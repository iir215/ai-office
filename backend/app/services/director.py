import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import Agent
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.invite import Invite
from app.models.message import Message
from app.models.role import Role
from app.models.task import Task
from app.services.openai_client import client
from app.services.queue import task_queue
from app.workers.instagram_jobs import generate_instagram_post
from app.workers.tasks import run_agent_task


DIRECTOR_SYSTEM_PROMPT = (
    "You are the Director, an AI manager overseeing a team of AI worker "
    "agents for this company. You talk directly to the business owner: "
    "report status, give advice, and answer questions yourself when you "
    "can. When a request needs a specific worker agent's expertise, use "
    "the delegate_task tool instead of doing the work yourself. Use "
    "list_agents to see which workers are available before delegating. "
    "Use grant_telegram_access when the owner wants to give someone access "
    "to this company's bot by their Telegram username. Use "
    "create_instagram_post when the owner asks to create or publish "
    "Instagram content — the agent capable of it will generate an image "
    "and caption and send them to the owner for approval before anything "
    "is actually published."
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

    task_queue.enqueue(generate_instagram_post, agent.id, conversation.company_id, topic)

    return (
        f"{agent.name} is generating the post now and will send it to the owner "
        "on Telegram for approval before publishing."
    )


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
        {"role": "system", "content": director.system_prompt},
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
