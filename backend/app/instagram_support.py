import time

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.company import Company
from app.models.instagram_interaction import InstagramInteractionState
from app.services.instagram_accounts import InstagramCreds, get_creds, has_account, refresh_due_accounts
from app.services.openai_client import client
from app.services.telegram import notify_company

GRAPH_URL = "https://graph.instagram.com"


def has_replied_to_comment(db, comment_id: str) -> bool:
    return (
        db.query(InstagramInteractionState)
        .filter(InstagramInteractionState.kind == "comment")
        .filter(InstagramInteractionState.external_id == comment_id)
        .first()
        is not None
    )


def mark_comment_replied(db, comment_id: str) -> None:
    db.add(InstagramInteractionState(kind="comment", external_id=comment_id))
    db.commit()


def get_last_dm_message_id(db, conv_id: str) -> str | None:
    state = (
        db.query(InstagramInteractionState)
        .filter(InstagramInteractionState.kind == "dm")
        .filter(InstagramInteractionState.external_id == conv_id)
        .first()
    )
    return state.last_value if state else None


def set_last_dm_message_id(db, conv_id: str, message_id: str) -> None:
    state = (
        db.query(InstagramInteractionState)
        .filter(InstagramInteractionState.kind == "dm")
        .filter(InstagramInteractionState.external_id == conv_id)
        .first()
    )
    if state:
        state.last_value = message_id
    else:
        db.add(InstagramInteractionState(kind="dm", external_id=conv_id, last_value=message_id))
    db.commit()


def generate_reply(agent: Agent, company_name: str, context_type: str, text: str, author: str) -> str:
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": agent.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Клиент оставил {context_type} в Instagram {company_name}.\n"
                    f"От: {author}\nТекст: {text}\n\n"
                    f"Напиши короткий, дружелюбный ответ от лица {company_name}."
                ),
            },
        ],
    )
    return response.choices[0].message.content or "Спасибо за сообщение! Мы скоро ответим."


def check_comments(db, agent: Agent, company_name: str, creds: InstagramCreds) -> None:
    media_resp = httpx.get(
        f"{GRAPH_URL}/{creds.account_id}/media",
        params={"fields": "id", "limit": 10, "access_token": creds.token},
        timeout=15,
    )
    if media_resp.status_code != 200:
        return

    for media in media_resp.json().get("data", []):
        comments_resp = httpx.get(
            f"{GRAPH_URL}/{media['id']}/comments",
            params={"fields": "id,text,username,from,timestamp", "access_token": creds.token},
            timeout=15,
        )
        if comments_resp.status_code != 200:
            continue

        for comment in comments_resp.json().get("data", []):
            comment_id = comment["id"]
            from_id = str(comment.get("from", {}).get("id", ""))
            is_own = from_id == str(creds.account_id) or (
                creds.username is not None and comment.get("username") == creds.username
            )

            if is_own or has_replied_to_comment(db, comment_id):
                continue

            reply_text = generate_reply(
                agent, company_name, "комментарий", comment.get("text", ""), comment.get("username", "клиент")
            )

            reply_resp = httpx.post(
                f"{GRAPH_URL}/{comment_id}/replies",
                params={"message": reply_text, "access_token": creds.token},
                timeout=15,
            )
            mark_comment_replied(db, comment_id)

            if reply_resp.status_code == 200:
                notify_company(
                    db,
                    agent.company_id,
                    f"💬 [{agent.name}] Ответил на комментарий @{comment.get('username', '?')}:\n"
                    f"«{comment.get('text', '')[:120]}»\n→ «{reply_text[:200]}»",
                )


def check_dms(db, agent: Agent, company_name: str, creds: InstagramCreds) -> None:
    conv_resp = httpx.get(
        f"{GRAPH_URL}/{creds.account_id}/conversations",
        params={"access_token": creds.token},
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
                "access_token": creds.token,
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

        if from_id == str(creds.account_id):
            continue
        if get_last_dm_message_id(db, conv_id) == latest["id"]:
            continue

        reply_text = generate_reply(agent, company_name, "личное сообщение", latest.get("message", ""), "клиент")

        send_resp = httpx.post(
            f"{GRAPH_URL}/{creds.account_id}/messages",
            json={"recipient": {"id": from_id}, "message": {"text": reply_text}},
            params={"access_token": creds.token},
            timeout=15,
        )
        set_last_dm_message_id(db, conv_id, latest["id"])

        if send_resp.status_code == 200:
            notify_company(
                db,
                agent.company_id,
                f"✉️ [{agent.name}] Ответил в директ:\n"
                f"«{latest.get('message', '')[:120]}»\n→ «{reply_text[:200]}»",
            )


def main() -> None:
    interval = settings.INSTAGRAM_SUPPORT_POLL_INTERVAL_SECONDS
    print(f"Instagram support loop started, interval={interval}s")

    while True:
        db = SessionLocal()
        try:
            try:
                refresh_due_accounts(db)
            except Exception as exc:
                print(f"refresh_due_accounts failed: {exc}")

            companies = db.query(Company).filter(Company.is_active.is_(True)).all()
            for company in companies:
                if not has_account(company.id):
                    continue

                agent = (
                    db.query(Agent)
                    .filter(Agent.company_id == company.id)
                    .filter(Agent.handles_instagram_support.is_(True))
                    .filter(Agent.is_active.is_(True))
                    .first()
                )
                if not agent:
                    continue

                creds = get_creds(company.id)

                try:
                    check_comments(db, agent, company.name, creds)
                except Exception as exc:
                    print(f"check_comments failed for {company.name}: {exc}")

                try:
                    check_dms(db, agent, company.name, creds)
                except Exception as exc:
                    print(f"check_dms failed for {company.name}: {exc}")
        except Exception as exc:
            print(f"instagram_support loop error: {exc}")
        finally:
            db.close()

        time.sleep(interval)


if __name__ == "__main__":
    main()
