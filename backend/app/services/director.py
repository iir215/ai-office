import json
import os

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import Agent
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.invite import Invite
from app.models.message import Message
from app.models.pending_post import PendingPost
from app.models.role import Role
from app.models.task import Task
from app.services.openai_client import client
from app.services.instagram_accounts import has_account
from app.services.media_library import MAX_REFERENCES, get_assets, list_assets
from app.services.queue import task_queue
from app.workers.instagram_jobs import generate_instagram_post, generate_instagram_video_post
from app.workers.tasks import run_agent_task
from app.workers.video_edit_jobs import edit_instagram_video_post
from app.services.instagram import VIDEO_DIR
from app.services.video_editor import LAYOUTS, probe_duration, scene_cuts


DIRECTOR_SYSTEM_PROMPT = (
    "You are the Director, an AI manager overseeing a team of AI worker "
    "agents for this company. You talk directly to the business owner: "
    "report status, give advice, and answer questions yourself when you "
    "can. When a request needs a specific worker agent's expertise, use "
    "the delegate_task tool instead of doing the work yourself. Use "
    "list_agents to see which workers are available before delegating. "
    "Use grant_telegram_access when the owner wants to give someone access "
    "to this company's bot by their Telegram username. For Instagram "
    "content requests, first decide photo vs video: if the owner's wording "
    "mentions a video/clip/Reel — in Russian this includes 'ролик', "
    "'видео', 'видеопост', 'рилс', 'reels', or similar — treat it as a "
    "video request, NOT create_instagram_post. create_instagram_post is "
    "only for a still image/photo post (Russian: 'фото', 'картинка', "
    "'изображение', or no media type mentioned at all) — call it right "
    "away, no scenario step needed. "
    "\n\n"
    "For a VIDEO request, video generation costs real money per attempt, "
    "so never call create_instagram_video_post right away. Instead: first "
    "write a short scenario in the chat as plain text (2-4 sentences, in "
    "Russian, human-readable — what's shown, the mood/lighting, camera "
    "movement, and what the audio/soundscape should sound like) and ask "
    "the owner to confirm it. Do not call any tool in that turn. Only "
    "after the owner clearly approves (да, ок, давай, подходит, or "
    "similar) call create_instagram_video_post, passing the exact "
    "approved scenario text as the topic argument so generation matches "
    "what was agreed. If the owner asks for changes, revise the scenario "
    "text and ask again before generating anything. "
    "\n\n"
    "create_instagram_post generates an image and caption; "
    "create_instagram_video_post generates a short AI video with sound "
    "and caption and takes noticeably longer. Both send the result to the "
    "owner for approval and NEVER publish automatically."
)

# Appended to every Director's stored prompt at request time (the stored prompt
# is per company in the DB and would not pick up code changes otherwise).
VIDEO_EDIT_RULES = (
    "EDITING AN EXISTING REEL. You CAN edit finished videos (when the owner asks "
    "to fix a closing frame, a logo, a background colour or a slogan colour of a "
    "video, this is the tool; never answer that you cannot edit video, and do not "
    "delegate it with delegate_task). If he wants a clean closing card with the "
    "logo, a coloured background and a slogan, use ending_type=brand_card "
    "(free, no photos needed, colour 'mustard' is the logo's yellow); for a new "
    "filmed closing scene use ending_type=scene. In brand_card the headline "
    "lines are the slogan (black by default); the logo is placed automatically. "
    "Call "
    "list_video_posts to find the post (ids, status, caption), then "
    "edit_instagram_video_post. The edit keeps the first part of the video "
    "(keep_until_seconds), replaces the rest with a NEW closing scene generated "
    "from the owner's real photos (reference_media_ids from list_media — "
    "required), and burns animated text over the ending (headline, info line, "
    "pills) in a modern font. It costs real money (about $0.65 for the new "
    "5-second scene) and takes several minutes, so it is two-step: call "
    "edit_instagram_video_post (it only records the plan), then write the plan "
    "to the owner in plain Russian text, STOP and wait for his reply, and only "
    "after he approves call confirm_video_edit. The plan states: which post, how many seconds "
    "stay, how the new ending looks (camera, light, mood), and the EXACT texts "
    "in the requested language (e.g. Uzbek in Latin script, using the "
    "characters ʻ and ʼ for oʻ, gʻ, taʼm). Use only facts from your knowledge "
    "(address, hours, discounts) for the text; never invent them. Write ALL "
    "on-screen text in ONE script: for Uzbek use Latin script only (never mix "
    "with Cyrillic), translate everything including the address, and keep the "
    "brand's own slogans as the owner formulates them. In the plan state "
    "keep_until_seconds (pick the point where the original's last scene "
    "starts; if unsure, ask) and say "
    "which layout you use: bottom_stack puts all text on the lower part (good "
    "when the subject fills the upper frame), top_headline puts the headline "
    "above the subject. The result is sent to the owner for approval and is "
    "NEVER published automatically. Never say you cannot edit video."
)

PHOTO_LIBRARY_RULES = (
    "PHOTOS OF THE REAL BUSINESS. The owner keeps a photo library "
    "(food truck, premises, dishes) that he fills by sending photos to this "
    "bot in Telegram with a caption. Whenever a video (or any content) is "
    "about the real truck/venue/dishes, or the owner mentions photos, FIRST "
    "call list_media. If suitable photos exist, use them: put their ids in "
    "reference_media_ids when calling create_instagram_video_post, and say in "
    "the scenario which photos are used and that the real truck/venue from "
    "them will appear. If suitable photos do not exist, DO NOT invent the "
    "venue: ask the owner to send photos to this bot in Telegram (with a "
    "caption saying what is on them, e.g. 'фудтрак') and to tell you when "
    "done. Never claim that you cannot save photos: the bot saves every photo "
    "the owner sends into the library."
)

MAX_TOOL_ROUNDS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_agents",
            "description": "List the worker agents configured for this company, with their name and current status.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": "Assign a task to a specific worker agent. The agent works on it in the background and reports back later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Exact name of the worker agent to delegate to.",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "What the agent should do.",
                    },
                },
                "required": ["agent_name", "instructions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grant_telegram_access",
            "description": "Grant a person access to this company's Telegram bot by their Telegram username. They are linked automatically the next time they message the bot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "telegram_username": {
                        "type": "string",
                        "description": "Telegram username (with or without @) or t.me link of the person to grant access to.",
                    },
                    "role": {
                        "type": "string",
                        "description": "Role to assign: admin, manager, or employee. Defaults to employee if not specified.",
                    },
                },
                "required": ["telegram_username"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_instagram_post",
            "description": "Have the agent capable of Instagram publishing generate an image and caption for a post on a given topic. It is sent to the owner for approval and is NOT published automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "What the post should be about.",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_media",
            "description": "List the owner's photo library for this company (id and label of each photo: food truck, premises, dishes, ...).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_video_posts",
            "description": "List recent Reels video posts of this company (id, status, date, caption start). Use to find the post the owner means by 'yesterday's video' etc.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_instagram_video_post",
            "description": "STEP 1 of 2 for re-cutting an existing Reels video (keep its beginning, replace the ending with a new scene generated from the owner's real photos, overlay animated text). This call only RECORDS the plan: nothing starts and nothing is spent. After it, present the plan and exact texts to the owner, STOP, and wait for his reply; then call confirm_video_edit. The final video goes to the owner for approval and is NOT published automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_post_id": {"type": "integer", "description": "Id from list_video_posts."},
                    "keep_until_seconds": {
                        "type": "number",
                        "description": "How many seconds of the original to keep; everything after is replaced by the new ending.",
                    },
                    "ending_description": {
                        "type": "string",
                        "description": "Approved description of the new closing scene: what is shown, camera movement, light, mood. The real truck/venue from the photos appears in it.",
                    },
                    "reference_media_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Photo ids from list_media (required, up to 9).",
                    },
                    "headline": {
                        "type": "array",
                        "description": "Big text lines over the ending (1-2 short lines).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "color": {"type": "string", "enum": ["white", "yellow", "black"]},
                            },
                            "required": ["text"],
                        },
                    },
                    "info_line": {"type": "string", "description": "Small line under the headline, e.g. the address."},
                    "chips": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Short pills at the bottom, e.g. a discount and opening hours. The first is highlighted in yellow.",
                    },
                    "layout": {"type": "string", "enum": list(LAYOUTS)},
                    "ending_type": {
                        "type": "string",
                        "enum": ["scene", "brand_card"],
                        "description": "scene = new AI-generated closing scene from the owner's photos (about $0.65, needs reference_media_ids). brand_card = flat-colour card with the company logo in the middle and the headline/info texts under it (drawn locally, FREE, no photos needed) — use it when the owner asks for a logo on a coloured background / a clean closing card.",
                    },
                    "background_color": {
                        "type": "string",
                        "description": "brand_card only: 'mustard' (the logo's own yellow, default), 'black', 'white' or a #RRGGBB hex.",
                    },
                    "caption": {
                        "type": "string",
                        "description": "New post caption; omit to keep the original caption.",
                    },
                },
                "required": ["source_post_id", "keep_until_seconds", "ending_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_video_edit",
            "description": "STEP 2 of 2: start the video edit recorded by edit_instagram_video_post (costs about $0.65). Call it only when the owner has clearly approved the plan in a message he wrote AFTER you presented it; the system rejects the call otherwise.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_instagram_video_post",
            "description": "Have the agent capable of Instagram publishing generate a short AI video (Reels) with sound and a caption. Costs real money per generation and takes several minutes — only call this AFTER the owner has explicitly approved a scenario you proposed to them in chat. It is sent to the owner for approval and is NOT published automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The exact scenario text the owner already approved in chat (not just a short topic).",
                    },
                    "reference_media_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Ids from list_media of the photos that must appear in the video (up to 9). Use them whenever the video shows the real truck, venue or dishes.",
                    },
                },
                "required": ["topic"],
            },
        },
    },
]


def get_or_create_director(db: Session, company_id: int) -> Agent:
    director = (
        db.query(Agent)
        .filter(Agent.company_id == company_id)
        .filter(Agent.role_type == "director")
        .first()
    )

    if director:
        return director

    director = Agent(
        company_id=company_id,
        name="Director",
        role_type="director",
        system_prompt=DIRECTOR_SYSTEM_PROMPT,
        status="idle",
        is_active=True,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    return director


def get_or_create_conversation(
    db: Session,
    company_id: int,
    user_id: int,
    conversation_id: int | None,
) -> Conversation:
    if conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conversation:
            return conversation

    director = get_or_create_director(db, company_id)

    conversation = Conversation(
        company_id=company_id,
        user_id=user_id,
        director_agent_id=director.id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def _list_agents(db: Session, company_id: int) -> str:
    agents = (
        db.query(Agent)
        .filter(Agent.company_id == company_id)
        .filter(Agent.role_type == "worker")
        .filter(Agent.is_active.is_(True))
        .all()
    )

    if not agents:
        return "No worker agents are configured yet."

    return "\n".join(f"- {a.name} (status: {a.status})" for a in agents)


def _delegate_task(
    db: Session,
    conversation: Conversation,
    agent_name: str,
    instructions: str,
) -> str:
    agent = (
        db.query(Agent)
        .filter(Agent.company_id == conversation.company_id)
        .filter(Agent.role_type == "worker")
        .filter(Agent.name == agent_name)
        .first()
    )

    if not agent:
        return f"No worker agent named '{agent_name}' exists."

    task = Task(
        company_id=conversation.company_id,
        director_agent_id=conversation.director_agent_id,
        assigned_agent_id=agent.id,
        conversation_id=conversation.id,
        instructions=instructions,
        status="queued",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task_queue.enqueue(run_agent_task, task.id)

    return f"Task {task.id} queued for agent '{agent.name}'."


def _grant_telegram_access(db: Session, conversation: Conversation, username: str, role_name: str | None) -> str:
    username = username.strip().lstrip("@")
    if username.lower().startswith("http"):
        username = username.rstrip("/").split("/")[-1].lstrip("@")

    if not username:
        return "Could not parse a Telegram username from that."

    role = None
    if role_name:
        role = db.query(Role).filter(Role.name.ilike(role_name)).first()
    if not role:
        role = db.query(Role).filter(Role.name == "employee").first()
    if not role:
        return "No roles are configured in the system."

    existing = (
        db.query(Invite)
        .filter(Invite.company_id == conversation.company_id)
        .filter(Invite.telegram_username.ilike(username))
        .first()
    )
    if existing and existing.status == "accepted":
        return f"@{username} already has access to this company."
    if existing and existing.status == "pending":
        return f"An invite for @{username} already exists and is waiting for them to message the bot."

    invite = Invite(
        company_id=conversation.company_id,
        role_id=role.id,
        telegram_username=username,
        status="pending",
    )
    db.add(invite)
    db.commit()

    company = db.query(Company).filter(Company.id == conversation.company_id).first()
    return (
        f"Invite created for @{username} to join '{company.name}' as {role.name}. "
        "Access opens automatically as soon as they message the bot."
    )


def _create_instagram_post(db: Session, conversation: Conversation, topic: str) -> str:
    agent = (
        db.query(Agent)
        .filter(Agent.company_id == conversation.company_id)
        .filter(Agent.can_publish_instagram.is_(True))
        .filter(Agent.is_active.is_(True))
        .first()
    )

    if not agent:
        return "No agent with Instagram publishing capability is configured for this company."

    if not has_account(conversation.company_id):
        return (
            "Instagram publishing is not set up for this company (no Instagram account is "
            "connected). Tell the owner; do not try to work around it with delegate_task."
        )

    task_queue.enqueue(generate_instagram_post, agent.id, conversation.company_id, topic)

    return (
        f"{agent.name} is generating the post now and will send it to the owner "
        "on Telegram for approval before publishing."
    )


def _local_video_path(url: str) -> str | None:
    path = os.path.join(VIDEO_DIR, (url or "").rsplit("/", 1)[-1])
    return path if os.path.exists(path) else None


def _list_video_posts(db: Session, company_id: int) -> str:
    posts = (
        db.query(PendingPost)
        .filter(PendingPost.company_id == company_id, PendingPost.media_type == "REELS")
        .order_by(PendingPost.id.desc())
        .limit(10)
        .all()
    )
    if not posts:
        return "No video posts yet."
    lines = []
    for i, p in enumerate(posts):
        line = f"id={p.id} [{p.status}] {p.created_at:%Y-%m-%d %H:%M} UTC: {(p.caption or '')[:70]!r}"
        if i < 5:  # measuring costs a second or two per video
            path = _local_video_path(p.image_url)
            if path:
                try:
                    line += f" | duration={probe_duration(path):.1f}s, scenes start at {scene_cuts(path)} s"
                except Exception:
                    pass
        lines.append(line)
    return "\n".join(lines)


# Paid video edits are two-step and enforced here, not only in the prompt: the
# first call stores a proposal, the second (confirm_video_edit) runs it, and only
# if the owner has written another message in between. In-memory: a restart just
# means the Director proposes again.
_edit_proposals: dict[int, tuple[dict, int]] = {}


def _owner_message_count(db: Session, conversation: Conversation) -> int:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.sender_type == "user")
        .count()
    )


def _edit_instagram_video_post(db: Session, conversation: Conversation, args: dict, confirm: bool = False) -> str:
    if confirm:
        proposal = _edit_proposals.get(conversation.id)
        if not proposal:
            return (
                "There is no pending video-edit proposal. Call edit_instagram_video_post with the "
                "plan first, present it to the owner and wait for his approval."
            )
        args, proposed_at = proposal
        if _owner_message_count(db, conversation) <= proposed_at:
            return (
                "The owner has not answered yet. Present the plan and the exact texts to the owner now "
                "and STOP; call confirm_video_edit only after he approves in his next message."
            )
        del _edit_proposals[conversation.id]

    agent = (
        db.query(Agent)
        .filter(Agent.company_id == conversation.company_id)
        .filter(Agent.can_publish_instagram.is_(True))
        .filter(Agent.is_active.is_(True))
        .first()
    )
    if not agent:
        return "No agent with Instagram publishing capability is configured for this company."
    if not has_account(conversation.company_id):
        return (
            "Instagram publishing is not set up for this company (no Instagram account is "
            "connected). Tell the owner; do not try to work around it with delegate_task."
        )

    source = (
        db.query(PendingPost)
        .filter(PendingPost.id == int(args["source_post_id"]), PendingPost.company_id == conversation.company_id)
        .first()
    )
    if not source or source.media_type != "REELS":
        return "That post is not a Reels video of this company. Call list_video_posts and use an id it returns."

    ending_type = args.get("ending_type") or "scene"
    if ending_type not in ("scene", "brand_card"):
        ending_type = "scene"

    wanted = [int(i) for i in args.get("reference_media_ids") or []]
    found = get_assets(db, conversation.company_id, wanted)
    if ending_type == "scene" and (not wanted or len(found) != len(set(wanted))):
        return (
            "Reference photos are required and must come from list_media (this company's library, "
            f"at most {MAX_REFERENCES}). If there are none, ask the owner to send photos to the bot."
        )

    keep = float(args["keep_until_seconds"])
    snapped_note = ""
    path = _local_video_path(source.image_url)
    if path:
        duration = probe_duration(path)
        if not 1 <= keep <= duration - 1:
            return (
                f"keep_until_seconds={keep} is invalid: that video lasts {duration:.1f}s. Choose a value "
                f"between 1 and {duration - 1:.1f}, ideally where the last scene starts (see the scene "
                "start times in list_video_posts)."
            )
        # Cut on a scene boundary, otherwise a fragment of the old last scene remains.
        cuts = [c for c in scene_cuts(path) if 1 <= c <= duration - 1]
        nearest = min(cuts, key=lambda c: abs(c - keep), default=None)
        if nearest is not None and abs(nearest - keep) <= 2.5 and nearest != keep:
            snapped_note = f" The cut was moved from {keep}s to {nearest}s, the start of the scene; tell the owner {nearest}s."
            keep = nearest
        args = {**args, "keep_until_seconds": keep}

    layout = args.get("layout") or "bottom_stack"
    if layout not in LAYOUTS:
        layout = "bottom_stack"
    text = {
        "headline": args.get("headline") or [],
        "info_line": args.get("info_line") or "",
        "chips": args.get("chips") or [],
        "layout": layout,
    }

    if not confirm:
        _edit_proposals[conversation.id] = (args, _owner_message_count(db, conversation))
        return (
            f"Proposal saved.{snapped_note} NOTHING has been started and nothing has been spent. Now write the plan to "
            "the owner in plain Russian (which post, how many seconds stay, how the new ending looks, "
            "the layout, the EXACT on-screen texts, the cost: about $0.65 for a generated scene, free for a "
            "brand_card) and ask whether to start. "
            "STOP after asking. When the owner approves in his next message, call confirm_video_edit; "
            "if he asks for changes, call edit_instagram_video_post again with the corrected plan."
        )

    task_queue.enqueue(
        edit_instagram_video_post,
        agent.id,
        conversation.company_id,
        source.id,
        float(args["keep_until_seconds"]),
        args.get("ending_description", ""),
        [a.id for a in found],
        text,
        args.get("caption"),
        ending_type,
        args.get("background_color"),
        job_timeout=1200,
    )
    return (
        f"{agent.name} is editing post {source.id} now (about 5 minutes) and will send the new "
        "version to the owner on Telegram for approval before publishing."
    )


def _list_media(db: Session, company_id: int) -> str:
    assets = list_assets(db, company_id)
    if not assets:
        return "The photo library is empty: the owner has not sent any photos yet."
    return "\n".join(f"id={a.id}: {a.label}" for a in assets)


def _create_instagram_video_post(
    db: Session,
    conversation: Conversation,
    topic: str,
    reference_media_ids: list[int] | None = None,
) -> str:
    agent = (
        db.query(Agent)
        .filter(Agent.company_id == conversation.company_id)
        .filter(Agent.can_publish_instagram.is_(True))
        .filter(Agent.is_active.is_(True))
        .first()
    )

    if not agent:
        return "No agent with Instagram publishing capability is configured for this company."

    if not has_account(conversation.company_id):
        return (
            "Instagram publishing is not set up for this company (no Instagram account is "
            "connected). Tell the owner; do not try to work around it with delegate_task."
        )

    media_ids: list[int] = []
    if reference_media_ids:
        wanted = [int(i) for i in reference_media_ids]
        found = get_assets(db, conversation.company_id, wanted)
        if len(found) != len(set(wanted)):
            return (
                "Some of those photo ids are not in this company's library. Call list_media "
                f"and use only ids it returns (at most {MAX_REFERENCES})."
            )
        media_ids = [a.id for a in found]

    task_queue.enqueue(
        generate_instagram_video_post,
        agent.id,
        conversation.company_id,
        topic,
        reference_media_ids=media_ids or None,
        job_timeout=1200,
    )

    used = f" using {len(media_ids)} reference photo(s)" if media_ids else ""
    return (
        f"{agent.name} is generating the video now{used} (this takes a few minutes) and will "
        "send it to the owner on Telegram for approval before publishing."
    )


def _system_prompt(director: Agent, conversation: Conversation) -> str:
    prompt = f"{director.system_prompt}\n\n{PHOTO_LIBRARY_RULES}\n\n{VIDEO_EDIT_RULES}"
    if conversation.id in _edit_proposals:
        # Tool calls are not part of the chat history the model sees, so tell it explicitly.
        prompt += (
            "\n\nSTATE: a video-edit plan is recorded and waits for the owner's decision "
            "(nothing started yet). If the owner's latest message approves it (да, давай, "
            "запускай, ок...), call confirm_video_edit now and do not call "
            "edit_instagram_video_post again. If he wants changes, call "
            "edit_instagram_video_post with the corrected plan and present it again. "
            "If he declines, do nothing."
        )
    return prompt


def _build_history(db: Session, conversation: Conversation) -> list[dict]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    history = []
    for m in messages:
        role = "user" if m.sender_type == "user" else "assistant"
        history.append({"role": role, "content": m.content})

    return history


def handle_user_message(db: Session, conversation: Conversation, text: str) -> str:
    director = (
        db.query(Agent)
        .filter(Agent.id == conversation.director_agent_id)
        .first()
    )

    db.add(
        Message(
            conversation_id=conversation.id,
            sender_type="user",
            content=text,
        )
    )
    db.commit()

    messages = [
        {"role": "system", "content": _system_prompt(director, conversation)},
        *_build_history(db, conversation),
    ]

    reply_text = ""

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
        )

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls

        if not tool_calls:
            reply_text = choice.message.content or ""
            break

        messages.append(choice.message)

        for tool_call in tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")

            if tool_call.function.name == "list_agents":
                result = _list_agents(db, conversation.company_id)
            elif tool_call.function.name == "delegate_task":
                result = _delegate_task(
                    db,
                    conversation,
                    args.get("agent_name", ""),
                    args.get("instructions", ""),
                )
            elif tool_call.function.name == "grant_telegram_access":
                result = _grant_telegram_access(
                    db,
                    conversation,
                    args.get("telegram_username", ""),
                    args.get("role"),
                )
            elif tool_call.function.name == "create_instagram_post":
                result = _create_instagram_post(
                    db,
                    conversation,
                    args.get("topic", ""),
                )
            elif tool_call.function.name == "list_video_posts":
                result = _list_video_posts(db, conversation.company_id)
            elif tool_call.function.name == "edit_instagram_video_post":
                try:
                    result = _edit_instagram_video_post(db, conversation, args)
                except (KeyError, ValueError, TypeError) as exc:
                    result = f"Invalid arguments for edit_instagram_video_post: {exc!r}"
            elif tool_call.function.name == "confirm_video_edit":
                result = _edit_instagram_video_post(db, conversation, {}, confirm=True)
            elif tool_call.function.name == "list_media":
                result = _list_media(db, conversation.company_id)
            elif tool_call.function.name == "create_instagram_video_post":
                result = _create_instagram_video_post(
                    db,
                    conversation,
                    args.get("topic", ""),
                    args.get("reference_media_ids"),
                )
            else:
                result = f"Unknown tool: {tool_call.function.name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
    else:
        reply_text = (
            "I looked into this but couldn't finish within the allowed "
            "number of steps. Please try rephrasing your request."
        )

    db.add(
        Message(
            conversation_id=conversation.id,
            sender_type="agent",
            agent_id=director.id,
            content=reply_text,
        )
    )
    db.commit()

    return reply_text
