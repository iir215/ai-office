import httpx
from sqlalchemy.orm import Session

from app.core.config import settings


def send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> dict | None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return None

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    resp = httpx.post(url, json=payload, timeout=10)
    try:
        return resp.json().get("result")
    except Exception:
        return None


def edit_message(chat_id: str, message_id: int, text: str, reply_markup: dict | None = None) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": reply_markup if reply_markup is not None else {"inline_keyboard": []},
    }

    httpx.post(url, json=payload, timeout=10)


def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"

    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    httpx.post(url, json=payload, timeout=10)


def notify_company(db: Session, company_id: int, text: str, reply_markup: dict | None = None) -> list[dict]:
    if not settings.TELEGRAM_BOT_TOKEN:
        return []

    from app.models.user import User

    chat_ids = (
        db.query(User.telegram_chat_id)
        .filter(User.company_id == company_id)
        .filter(User.telegram_chat_id.isnot(None))
        .distinct()
        .all()
    )

    sent = []
    for (chat_id,) in chat_ids:
        result = send_message(chat_id, text, reply_markup)
        if result:
            sent.append({"chat_id": chat_id, "message_id": result["message_id"]})

    return sent
