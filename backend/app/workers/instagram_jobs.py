import json

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.pending_post import PendingPost
from app.services.instagram import create_media_container, generate_and_host_image
from app.services.openai_client import client
from app.services.telegram import notify_company


def generate_instagram_post(agent_id: int, company_id: int, topic: str) -> None:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
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
                f"Аппетитная фотография для Instagram уличного стрит-фастфуда QARS на тему: {topic}. "
                "Фотореалистично, яркое освещение, крупный план, аппетитно."
            )
            image_url = generate_and_host_image(image_prompt)
            container_id = create_media_container(image_url, caption)

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
            agent.status = "idle"
            db.commit()
            notify_company(db, company_id, f"[{agent.name}] Не удалось подготовить пост: {exc}")
    finally:
        db.close()
