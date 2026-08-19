import time

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.company import Company
from app.services.openai_client import client
from app.services.telegram import notify_company

GRAPH_URL = "https://graph.instagram.com"

# In-memory dedup state; lost on restart, acceptable for v1.
replied_comment_ids: set[str] = set()
last_dm_message_id: dict[str, str] = {}


def generate_reply(agent: Agent, context_type: str, text: str, author: str) -> str:
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": agent.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Клиент оставил {context_type} в Instagram QARS.\n"
                    f"От: {author}\nТекст: {text}\n\n"
                    "Напиши короткий, дружелюбный ответ от лица QARS."
                ),
            },
        ],
    )
    return response.choices[0].message.content or "Спасибо за сообщение! Мы скоро ответим."


def check_comments(db, agent: Agent) -> None:
    media_resp = httpx.get(
        f"{GRAPH_URL}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/media",
        params={"fields": "id", "limit": 10, "access_token": settings.INSTAGRAM_ACCESS_TOKEN},
        timeout=15,
    )
    if media_resp.status_code != 200:
        return

    for media in media_resp.json().get("data", []):
        comments_resp = httpx.get(
            f"{GRAPH_URL}/{media['id']}/comments",
            params={"fields": "id,text,username,from,timestamp", "access_token": settings.INSTAGRAM_ACCESS_TOKEN},
            timeout=15,
        )
        if comments_resp.status_code != 200:
            continue

        for comment in comments_resp.json().get("data", []):
            comment_id = comment["id"]
            from_id = str(comment.get("from", {}).get("id", ""))

            if from_id == str(settings.INSTAGRAM_BUSINESS_ACCOUNT_ID) or comment_id in replied_comment_ids:
                continue

            reply_text = generate_reply(
                agent, "комментарий", comment.get("text", ""), comment.get("username", "клиент")
            )

            reply_resp = httpx.post(
                f"{GRAPH_URL}/{comment_id}/replies",
                params={"message": reply_text, "access_token": settings.INSTAGRAM_ACCESS_TOKEN},
                timeout=15,
            )
            replied_comment_ids.add(comment_id)

            if reply_resp.status_code == 200:
                notify_company(
                    db,
                    agent.company_id,
                    f"💬 [{agent.name}] Ответил на комментарий @{comment.get('username', '?')}:\n"
                    f"«{comment.get('text', '')[:120]}»\n→ «{reply_text[:200]}»",
                )


def check_dms(db, agent: Agent) -> None:
    conv_resp = httpx.get(
        f"{GRAPH_URL}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/conversations",
        params={"access_token": settings.INSTAGRAM_ACCESS_TOKEN},
        timeout=15,
    )
    if conv_resp.status_code != 200:
        return

    for conv in conv_resp.json().get("data", []):
        conv_id = conv["id"]
        messages_resp = httpx.get(
            f"{GRAPH_URL}/{conv_id}",
            params={
                "fields": "messages{id,from,to,message,created_time}",
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=15,
        )
        if messages_resp.status_code != 200:
            continue

        messages = messages_resp.json().get("messages", {}).get("data", [])
        if not messages:
            continue

        latest = messages[0]
        from_id = str(latest.get("from", {}).get("id", ""))

        if from_id == str(settings.INSTAGRAM_BUSINESS_ACCOUNT_ID):
            continue
        if last_dm_message_id.get(conv_id) == latest["id"]:
            continue

        reply_text = generate_reply(agent, "личное сообщение", latest.get("message", ""), "клиент")

        send_resp = httpx.post(
            f"{GRAPH_URL}/{settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}/messages",
            json={"recipient": {"id": from_id}, "message": {"text": reply_text}},
            params={"access_token": settings.INSTAGRAM_ACCESS_TOKEN},
            timeout=15,
        )
        last_dm_message_id[conv_id] = latest["id"]

        if send_resp.status_code == 200:
            notify_company(
                db,
                agent.company_id,
                f"✉️ [{agent.name}] Ответил в директ:\n"
                f"«{latest.get('message', '')[:120]}»\n→ «{reply_text[:200]}»",
            )


def main() -> None:
    if not settings.INSTAGRAM_ACCESS_TOKEN:
        print("INSTAGRAM_ACCESS_TOKEN is not set, instagram_support will not start.")
        return

    interval = settings.INSTAGRAM_SUPPORT_POLL_INTERVAL_SECONDS
    print(f"Instagram support loop started, interval={interval}s")

    while True:
        db = SessionLocal()
        try:
            companies = db.query(Company).filter(Company.is_active.is_(True)).all()
            for company in companies:
                agent = (
                    db.query(Agent)
                    .filter(Agent.company_id == company.id)
                    .filter(Agent.handles_instagram_support.is_(True))
                    .filter(Agent.is_active.is_(True))
                    .first()
                )
                if not agent:
                    continue

                try:
                    check_comments(db, agent)
                except Exception as exc:
                    print(f"check_comments failed: {exc}")

                try:
                    check_dms(db, agent)
                except Exception as exc:
                    print(f"check_dms failed: {exc}")
        except Exception as exc:
            print(f"instagram_support loop error: {exc}")
        finally:
            db.close()

        time.sleep(interval)


if __name__ == "__main__":
    main()
