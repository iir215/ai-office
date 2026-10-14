import json
import os
import tempfile
import uuid

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.pending_post import PendingPost
from app.services.instagram import (
    VIDEO_DIR,
    create_video_container,
    wait_for_video_container_ready,
)
from app.services.instagram_accounts import has_account
from app.services.media_library import as_data_uri, get_assets
from app.services.minimax_video import generate_video
from app.services.telegram import notify_company
from app.services.video_editor import (
    TextSpec,
    probe_duration,
    recut_with_end_card,
    recut_with_new_ending,
)
from app.workers.instagram_jobs import _build_video_prompt

ENDING_SECONDS = 5


def _source_video(url: str, tmp: str) -> str:
    """Our hosted Reels live in static/videos; fall back to downloading the URL."""
    local = os.path.join(VIDEO_DIR, url.rsplit("/", 1)[-1])
    if os.path.exists(local):
        return local
    path = os.path.join(tmp, "source.mp4")
    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def edit_instagram_video_post(
    agent_id: int,
    company_id: int,
    source_post_id: int,
    keep_seconds: float,
    ending_description: str,
    reference_media_ids: list[int],
    text: dict | None = None,
    caption: str | None = None,
    ending_type: str = "scene",
    background_color: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent or not has_account(company_id):
            return

        agent.status = "busy"
        db.commit()

        try:
            source = (
                db.query(PendingPost)
                .filter(PendingPost.id == source_post_id, PendingPost.company_id == company_id)
                .first()
            )
            if not source or source.media_type != "REELS":
                raise ValueError(f"post {source_post_id} is not a Reels video of this company")

            spec = TextSpec(**(text or {}))
            with tempfile.TemporaryDirectory() as tmp:
                source_path = _source_video(source.image_url, tmp)
                keep = min(float(keep_seconds), probe_duration(source_path))
                os.makedirs(VIDEO_DIR, exist_ok=True)
                filename = f"{uuid.uuid4().hex}.mp4"
                dst = os.path.join(VIDEO_DIR, filename)

                if ending_type == "brand_card":
                    # Flat-colour card with the logo and text: drawn locally, no AI, no cost.
                    recut_with_end_card(source_path, dst, keep, spec, company_id, background_color)
                else:
                    photos = get_assets(db, company_id, reference_media_ids)
                    if not photos:
                        raise ValueError("no reference photos found for the new ending")
                    prompt = _build_video_prompt(ending_description, with_references=True)
                    ending_bytes = generate_video(
                        prompt,
                        duration=ENDING_SECONDS,
                        reference_images=[as_data_uri(a) for a in photos],
                    )
                    ending_path = os.path.join(tmp, "ending.mp4")
                    with open(ending_path, "wb") as f:
                        f.write(ending_bytes)
                    recut_with_new_ending(source_path, ending_path, dst, keep, spec, company_id)

            video_url = f"{settings.PUBLIC_BASE_URL}/ui/videos/{filename}"
            post_caption = caption or source.caption
            container_id = create_video_container(company_id, video_url, post_caption)
            wait_for_video_container_ready(company_id, container_id)

            pending = PendingPost(
                company_id=company_id,
                agent_id=agent.id,
                instagram_container_id=container_id,
                image_url=video_url,
                caption=post_caption,
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
                f"✂️ [{agent.name}] Отредактированное видео (из поста №{source_post_id}) готово к согласованию.\n\n"
                f"Подпись:\n{post_caption}\n\n"
                f"Видео: {video_url}",
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
            print(f"edit_instagram_video_post failed for agent {agent.id}: {exc!r}")
            agent.status = "idle"
            db.commit()
            try:
                notify_company(db, company_id, f"[{agent.name}] Не удалось отредактировать видео: {exc}")
            except Exception as notify_exc:
                print(f"notify_company also failed: {notify_exc!r}")
    finally:
        db.close()
