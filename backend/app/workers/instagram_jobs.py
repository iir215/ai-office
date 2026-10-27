import json

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.pending_post import PendingPost
from app.services.instagram import (
    create_media_container,
    create_video_container,
    generate_and_host_image,
    host_video,
    wait_for_video_container_ready,
)
from app.services.instagram_accounts import has_account
from app.services.media_library import as_data_uri, get_assets
from app.services.video_gen import generate_video, generate_video_costed
from app.services.openai_client import client
from app.services.telegram import notify_company


def _abort_without_instagram(db, agent: Agent, company_id: int) -> bool:
    # Checked before any paid generation (MiniMax video, image model) starts.
    if has_account(company_id):
        return False
    try:
        notify_company(
            db,
            company_id,
            f"[{agent.name}] Instagram не подключён для этой компании — публикация невозможна.",
        )
    except Exception as exc:
        print(f"notify_company failed: {exc!r}")
    return True

VIDEO_PROMPT_SYSTEM = (
    "You write shot-ready prompts for the MiniMax-H3 video generation model, "
    "which generates video with synchronized audio in the same pass. Given a "
    "short topic, expand it into a single detailed English prompt (max ~400 "
    "characters) describing one continuous shot: what's in frame, "
    "lighting/mood, camera movement using MiniMax's supported bracket syntax "
    "like [Pan left], [Zoom in], [Push in], [Static shot], [Tracking shot], "
    "and a brief cue for the ambient sound/sizzle/music mood so the "
    "generated audio matches the scene. The subject is street fast-food "
    "(Bonch burgers brand): food close-ups, appetizing, photorealistic. Output ONLY "
    "the prompt text, no preamble, no quotes."
)


VIDEO_PROMPT_WITH_PHOTOS_SYSTEM = (
    "You write shot-ready prompts for the MiniMax-H3 reference-to-video model, "
    "which generates video with synchronized audio. Photos of the owner's REAL "
    "business (food truck, premises, dishes) are attached to the generation as "
    "references. Given the approved scenario, write ONE detailed English prompt "
    "(up to ~1800 characters) that: (1) states that the real truck/venue from the "
    "reference photos must appear exactly as in the photos - same shape, colors, "
    "logo, icons and equipment - and that no extra signs, text or invented "
    "storefronts are allowed; (2) follows the scenario's shots, mood, lighting and "
    "visual style (if the scenario asks for a stylized look such as pixel/voxel, "
    "apply it to the whole scene; otherwise make it photorealistic and cinematic); "
    "(3) uses MiniMax bracket camera syntax like [Push in], [Pan right], "
    "[Tracking shot]; (4) ends with a short cue for ambient sound/music. "
    "Output ONLY the prompt text, no preamble, no quotes."
)


def _build_video_prompt(topic: str, with_references: bool = False) -> str:
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": VIDEO_PROMPT_WITH_PHOTOS_SYSTEM if with_references else VIDEO_PROMPT_SYSTEM,
            },
            {"role": "user", "content": topic},
        ],
    )
    prompt = (response.choices[0].message.content or "").strip()
    return prompt or (
        f"Appetizing close-up shot of street fast-food, topic: {topic}. "
        "Photorealistic, vibrant lighting, appetizing food styling. [Push in]"
    )


def generate_instagram_post(agent_id: int, company_id: int, topic: str) -> None:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return

        if _abort_without_instagram(db, agent, company_id):
            return

        agent.status = "busy"
        db.commit()

        try:
            caption_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": agent.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Подготовь подпись (caption) для поста в Instagram на тему: {topic}. "
                            "Только текст подписи, без картинки, коротко и по делу, в стиле бренда, "
                            "можно с уместными эмодзи и хэштегами."
                        ),
                    },
                ],
            )
            caption = caption_response.choices[0].message.content or topic

            image_prompt = (
                f"Аппетитная фотография для Instagram уличного стрит-фастфуда Bonch burgers на тему: {topic}. "
                "Фотореалистично, яркое освещение, крупный план, аппетитно. "
                "Оставь правый нижний угол кадра свободным: туда накладывается логотип."
            )
            image_url = generate_and_host_image(image_prompt, company_id)
            container_id = create_media_container(company_id, image_url, caption)

            pending = PendingPost(
                company_id=company_id,
                agent_id=agent.id,
                instagram_container_id=container_id,
                image_url=image_url,
                caption=caption,
                status="pending",
            )
            db.add(pending)
            agent.status = "idle"
            db.commit()
            db.refresh(pending)

            sent = notify_company(
                db,
                company_id,
                f"📸 [{agent.name}] Пост готов к согласованию.\n\n"
                f"Подпись:\n{caption}\n\n"
                f"Фото: {image_url}",
                reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "✅ Опубликовать", "callback_data": f"post_approve:{pending.id}"},
                            {"text": "❌ Отклонить", "callback_data": f"post_reject:{pending.id}"},
                        ]
                    ]
                },
            )
            pending.notified_messages = json.dumps(sent)
            db.commit()
        except Exception as exc:
            print(f"generate_instagram_post failed for agent {agent.id}: {exc!r}")
            agent.status = "idle"
            db.commit()
            try:
                notify_company(db, company_id, f"[{agent.name}] Не удалось подготовить пост: {exc}")
            except Exception as notify_exc:
                print(f"notify_company also failed: {notify_exc!r}")
    finally:
        db.close()


def generate_instagram_video_post(
    agent_id: int,
    company_id: int,
    topic: str,
    reference_images: list[str] | None = None,
    video_prompt: str | None = None,
    reference_media_ids: list[int] | None = None,
) -> None:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return

        if _abort_without_instagram(db, agent, company_id):
            return

        agent.status = "busy"
        db.commit()

        try:
            caption_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": agent.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Подготовь подпись (caption) для видео-поста (Reels) в Instagram на тему: {topic}. "
                            "Только текст подписи, коротко и по делу, в стиле бренда, "
                            "можно с уместными эмодзи и хэштегами."
                        ),
                    },
                ],
            )
            caption = caption_response.choices[0].message.content or topic
            # An explicit prompt (e.g. a custom visual style built around
            # reference photos) replaces the default photoreal food prompt.
            if reference_media_ids:
                reference_images = [
                    as_data_uri(a) for a in get_assets(db, company_id, reference_media_ids)
                ]
            video_prompt = video_prompt or _build_video_prompt(topic, with_references=bool(reference_images))
            video_bytes, cost_usd = generate_video_costed(video_prompt, reference_images=reference_images)
            video_url = host_video(video_bytes, company_id)
            container_id = create_video_container(company_id, video_url, caption)
            wait_for_video_container_ready(company_id, container_id)

            pending = PendingPost(
                company_id=company_id,
                agent_id=agent.id,
                instagram_container_id=container_id,
                image_url=video_url,
                caption=caption,
                status="pending",
                media_type="REELS",
            )
            db.add(pending)
            agent.status = "idle"
            db.commit()
            db.refresh(pending)

            sent = notify_company(
                db,
                company_id,
                f"🎬 [{agent.name}] Видео готово к согласованию.\n\n"
                f"Подпись:\n{caption}\n\n"
                f"Видео: {video_url}"
                + (f"\n\nСтоимость генерации ≈ ${cost_usd:.2f}" if cost_usd else ""),
                reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "✅ Опубликовать", "callback_data": f"post_approve:{pending.id}"},
                            {"text": "❌ Отклонить", "callback_data": f"post_reject:{pending.id}"},
                        ]
                    ]
                },
            )
            pending.notified_messages = json.dumps(sent)
            db.commit()
        except Exception as exc:
            print(f"generate_instagram_video_post failed for agent {agent.id}: {exc!r}")
            agent.status = "idle"
            db.commit()
            try:
                notify_company(db, company_id, f"[{agent.name}] Не удалось подготовить видео-пост: {exc}")
            except Exception as notify_exc:
                print(f"notify_company also failed: {notify_exc!r}")
    finally:
        db.close()
