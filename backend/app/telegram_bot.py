import json
import secrets
import time

import bcrypt
import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.company import Company
from app.models.invite import Invite
from app.models.pending_post import PendingPost
from app.models.user import User
from app.services.director import get_or_create_conversation, handle_user_message
from app.services.instagram import get_permalink, publish_media
from app.services.telegram import answer_callback_query, edit_message, notify_company, send_message

API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

BTN_INTERLOCUTOR = "🧑‍💼 Собеседник"
BTN_SWITCH_COMPANY = "🏢 Сменить компанию"
BTN_NEW_CHAT = "🔄 Новый диалог"
BTN_AGENTS = "📋 Агенты"
BTN_NEW_AGENT = "➕ Новый агент"
BTN_BACK = "⬅️ Назад"
BTN_DIRECTOR = "Director"

# In-memory per-chat state; lost on restart, acceptable for v1.
active_company: dict[int, int] = {}
active_interlocutor: dict[int, str] = {}
active_conversations: dict[tuple[int, int], int] = {}
pending_agent_creation: dict[int, dict] = {}
menu_state: dict[int, str] = {}


def get_updates(offset: int) -> list[dict]:
    resp = httpx.get(
        f"{API_URL}/getUpdates",
        params={"offset": offset, "timeout": 25},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


def get_linked_users(db, chat_id: int) -> list[User]:
    return db.query(User).filter(User.telegram_chat_id == str(chat_id)).all()


def get_active_user(db, chat_id: int) -> User | None:
    users = get_linked_users(db, chat_id)
    if not users:
        return None

    company_id = active_company.get(chat_id)
    if company_id:
        for u in users:
            if u.company_id == company_id:
                return u

    active_company[chat_id] = users[0].company_id
    return users[0]


def main_keyboard(chat_id: int) -> dict:
    interlocutor = active_interlocutor.get(chat_id, BTN_DIRECTOR)
    return {
        "keyboard": [
            [f"{BTN_INTERLOCUTOR}: {interlocutor}"],
            [BTN_SWITCH_COMPANY, BTN_NEW_CHAT],
            [BTN_AGENTS, BTN_NEW_AGENT],
        ],
        "resize_keyboard": True,
    }


def company_keyboard(users: list[User]) -> dict:
    rows = [[u.company.name] for u in users]
    rows.append([BTN_BACK])
    return {"keyboard": rows, "resize_keyboard": True}


def interlocutor_keyboard(agents: list[Agent]) -> dict:
    rows = [[BTN_DIRECTOR]] + [[a.name] for a in agents]
    rows.append([BTN_BACK])
    return {"keyboard": rows, "resize_keyboard": True}


def worker_agents(db, company_id: int) -> list[Agent]:
    return (
        db.query(Agent)
        .filter(Agent.company_id == company_id)
        .filter(Agent.role_type == "worker")
        .filter(Agent.is_active.is_(True))
        .all()
    )


def handle_new_agent_step(db, chat_id: int, company_id: int, text: str) -> None:
    state = pending_agent_creation[chat_id]

    if state["step"] == "name":
        state["name"] = text.strip()
        state["step"] = "prompt"
        send_message(chat_id, f"Хорошо, агент «{state['name']}». Теперь опиши одним сообщением, что он должен делать (это станет его системным промптом).")
        return

    name = state["name"]
    prompt = text.strip()
    del pending_agent_creation[chat_id]

    existing = (
        db.query(Agent)
        .filter(Agent.company_id == company_id)
        .filter(Agent.name == name)
        .first()
    )
    if existing:
        send_message(chat_id, f"Агент с именем «{name}» уже есть в команде.", main_keyboard(chat_id))
        return

    agent = Agent(
        company_id=company_id,
        name=name,
        role_type="worker",
        system_prompt=prompt,
        status="idle",
        is_active=True,
        notify_owner=False,
    )
    db.add(agent)
    db.commit()
    send_message(chat_id, f"Готово! Агент «{name}» добавлен в команду.", main_keyboard(chat_id))


def try_accept_invite(db, chat_id: int, from_user: dict) -> User | None:
    username = (from_user.get("username") or "").strip().lstrip("@")
    if not username:
        return None

    invite = (
        db.query(Invite)
        .filter(Invite.telegram_username.ilike(username))
        .filter(Invite.status == "pending")
        .first()
    )
    if not invite:
        return None

    full_name = " ".join(
        part for part in [from_user.get("first_name"), from_user.get("last_name")] if part
    ).strip() or username

    user = User(
        company_id=invite.company_id,
        role_id=invite.role_id,
        full_name=full_name,
        email=f"tg_{chat_id}@telegram.local",
        password_hash=bcrypt.hashpw(secrets.token_hex(16).encode(), bcrypt.gensalt()).decode(),
        is_active=True,
        telegram_chat_id=str(chat_id),
    )
    db.add(user)
    invite.status = "accepted"
    db.commit()
    db.refresh(user)

    company = db.query(Company).filter(Company.id == invite.company_id).first()
    try:
        notify_company(db, invite.company_id, f"✅ {full_name} (@{username}) получил доступ к «{company.name}» по приглашению.")
    except Exception:
        pass

    return user


def handle_callback(db, callback: dict) -> None:
    callback_id = callback["id"]
    data = callback.get("data", "")

    try:
        action, pending_id_str = data.split(":")
        pending_id = int(pending_id_str)
    except (ValueError, KeyError):
        answer_callback_query(callback_id)
        return

    pending = db.query(PendingPost).filter(PendingPost.id == pending_id).first()

    if not pending or pending.status != "pending":
        answer_callback_query(callback_id, "Уже обработано или не найдено")
        return

    if action == "post_approve":
        try:
            media_id = publish_media(pending.instagram_container_id)
            pending.status = "published"
            db.commit()
            permalink = get_permalink(media_id)
            answer_callback_query(callback_id, "Опубликовано!")
            result_line = f"✅ Опубликовано: {permalink}"
        except Exception as exc:
            pending.status = "failed"
            db.commit()
            answer_callback_query(callback_id, "Ошибка публикации")
            result_line = f"❌ Не удалось опубликовать: {exc}"
    elif action == "post_reject":
        pending.status = "rejected"
        db.commit()
        answer_callback_query(callback_id, "Отклонено")
        result_line = "❌ Отклонено, публикация не выполнена."
    else:
        answer_callback_query(callback_id)
        return

    final_text = (
        f"📸 Пост:\n\n{pending.caption}\n\nФото: {pending.image_url}\n\n{result_line}"
    )

    for item in json.loads(pending.notified_messages or "[]"):
        try:
            edit_message(item["chat_id"], item["message_id"], final_text)
        except Exception:
            pass


def handle_message(db, chat_id: int, text: str, from_user: dict | None = None) -> None:
    users = get_linked_users(db, chat_id)
    if not users:
        new_user = try_accept_invite(db, chat_id, from_user or {})
        if new_user:
            send_message(chat_id, f"Добро пожаловать! У тебя открыт доступ к «{new_user.company.name}».", main_keyboard(chat_id))
            return
        send_message(chat_id, "Этот Telegram-аккаунт пока не привязан ни к одной компании в системе.")
        return

    menu = menu_state.get(chat_id)

    if text in ("/start", "/help"):
        menu_state.pop(chat_id, None)
        user = get_active_user(db, chat_id)
        send_message(chat_id, f"Привет! Сейчас говорим от лица компании «{user.company.name}».", main_keyboard(chat_id))
        return

    if text == BTN_BACK:
        menu_state.pop(chat_id, None)
        send_message(chat_id, "Ок.", main_keyboard(chat_id))
        return

    if text == BTN_SWITCH_COMPANY:
        menu_state[chat_id] = "company"
        send_message(chat_id, "Выбери компанию:", company_keyboard(users))
        return

    if menu == "company":
        chosen = next((u for u in users if u.company.name == text), None)
        if not chosen:
            send_message(chat_id, "Не узнал компанию, выбери из списка.", company_keyboard(users))
            return
        active_company[chat_id] = chosen.company_id
        active_interlocutor.pop(chat_id, None)
        menu_state.pop(chat_id, None)
        send_message(chat_id, f"Переключился на «{chosen.company.name}».", main_keyboard(chat_id))
        return

    user = get_active_user(db, chat_id)

    if text.startswith(BTN_INTERLOCUTOR):
        menu_state[chat_id] = "interlocutor"
        send_message(chat_id, "С кем говорить?", interlocutor_keyboard(worker_agents(db, user.company_id)))
        return

    if menu == "interlocutor":
        agents = worker_agents(db, user.company_id)
        if text == BTN_DIRECTOR:
            active_interlocutor.pop(chat_id, None)
        elif any(a.name == text for a in agents):
            active_interlocutor[chat_id] = text
        else:
            send_message(chat_id, "Не узнал агента, выбери из списка.", interlocutor_keyboard(agents))
            return
        menu_state.pop(chat_id, None)
        send_message(chat_id, f"Теперь говоришь с: {text}", main_keyboard(chat_id))
        return

    if text == BTN_NEW_CHAT or text == "/newchat":
        active_conversations.pop((chat_id, user.company_id), None)
        send_message(chat_id, "Начинаем новый диалог с Director.", main_keyboard(chat_id))
        return

    if text == BTN_AGENTS or text == "/agents":
        agents = db.query(Agent).filter(Agent.company_id == user.company_id).all()
        if not agents:
            send_message(chat_id, "Пока нет ни одного агента.", main_keyboard(chat_id))
            return
        lines = [
            f"• {a.name} ({'Director' if a.role_type == 'director' else 'агент'}) — {a.status}"
            for a in agents
        ]
        send_message(chat_id, "\n".join(lines), main_keyboard(chat_id))
        return

    if text == BTN_NEW_AGENT or text == "/newagent":
        pending_agent_creation[chat_id] = {"step": "name"}
        send_message(chat_id, "Как назвать нового агента?")
        return

    if chat_id in pending_agent_creation:
        handle_new_agent_step(db, chat_id, user.company_id, text)
        return

    interlocutor = active_interlocutor.get(chat_id)
    outgoing = f"@{interlocutor} {text}" if interlocutor else text

    conv_key = (chat_id, user.company_id)
    conversation = get_or_create_conversation(db, user.company_id, user.id, active_conversations.get(conv_key))
    active_conversations[conv_key] = conversation.id

    reply = handle_user_message(db, conversation, outgoing)
    send_message(chat_id, reply, main_keyboard(chat_id))


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set, telegram_bot will not start.")
        return

    offset = 0
    initial = get_updates(0)
    if initial:
        offset = initial[-1]["update_id"] + 1

    print("Telegram bot polling started.")
    while True:
        try:
            updates = get_updates(offset)
        except Exception as exc:
            print(f"getUpdates failed: {exc}")
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1

            callback = update.get("callback_query")
            if callback:
                db = SessionLocal()
                try:
                    handle_callback(db, callback)
                except Exception as exc:
                    print(f"callback handling failed: {exc}")
                finally:
                    db.close()
                continue

            message = update.get("message")
            if not message or "text" not in message:
                continue

            chat_id = message["chat"]["id"]
            text = message["text"]
            from_user = message.get("from", {})

            db = SessionLocal()
            try:
                handle_message(db, chat_id, text, from_user)
            except Exception as exc:
                send_message(chat_id, f"Произошла ошибка: {exc}")
            finally:
                db.close()


if __name__ == "__main__":
    main()
