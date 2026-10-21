"""The Bonch Burgers bot (@bonchburgersbot).

For guests: greets them and opens the ordering Mini App, and sends order status updates.
For the team: add the bot to the kitchen group and send /orders_here there (only a person
linked to the company in AION can do it); from then on every order arrives in that group
with Accept / Ready / Done / Cancel buttons. /orders_off in the group stops it.
"""
import time

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.shop_order import ShopOrder
from app.models.team_chat import TeamChat
from app.models.user import User
from app.services.shop import apply_action, expire_unpaid, team_chats, tg_api

API_URL = f"https://api.telegram.org/bot{settings.SHOP_BOT_TOKEN}"

HELLO = {
    "ru": "Добро пожаловать в Bonch Burgers! 🍔\nВыбирайте блюда, оплачивайте онлайн и забирайте у фудтрака или заказывайте доставку.",
    "uz": "Bonch Burgers’ga xush kelibsiz! 🍔\nTaomlarni tanlang, onlayn to‘lang va foodtruckdan olib keting yoki yetkazib berishni buyurtma qiling.",
}
BUTTON = {"ru": "🍔 Открыть меню", "uz": "🍔 Menyuni ochish"}


def app_url() -> str:
    return f"{settings.PUBLIC_BASE_URL}/ui/shop/?c={settings.SHOP_COMPANY_ID}"


def call(method: str, **payload) -> dict | None:
    return tg_api(settings.SHOP_BOT_TOKEN, method, **payload)


def get_updates(offset: int) -> list[dict]:
    resp = httpx.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", [])


def setup() -> None:
    # The blue button left of the input field opens the app in every chat with this bot.
    call(
        "setChatMenuButton",
        menu_button={"type": "web_app", "text": "Меню / Menyu", "web_app": {"url": app_url()}},
    )


def reply_start(message: dict) -> None:
    chat_id = message["chat"]["id"]
    lang = "uz" if str((message.get("from") or {}).get("language_code", "")).lower().startswith("uz") else "ru"
    call(
        "sendMessage",
        chat_id=chat_id,
        text=HELLO[lang],
        reply_markup={"inline_keyboard": [[{"text": BUTTON[lang], "web_app": {"url": app_url()}}]]},
    )


def is_staff(db, user_id: int) -> bool:
    """Staff = a person linked to this company in AION (their Telegram id is the private chat id)."""
    return (
        db.query(User)
        .filter(User.telegram_chat_id == str(user_id), User.company_id == settings.SHOP_COMPANY_ID)
        .first()
        is not None
    )


def handle_group_command(db, message: dict) -> None:
    chat = message["chat"]
    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return
    cmd = text.split()[0].split("@")[0].lower()
    if cmd not in ("/orders_here", "/orders_off"):
        return

    sender = (message.get("from") or {}).get("id")
    if not sender or not is_staff(db, sender):
        call("sendMessage", chat_id=chat["id"], text="Эту команду может отправить только сотрудник Bonch Burgers, подключённый в AION.")
        return

    existing = db.query(TeamChat).filter(TeamChat.chat_id == chat["id"]).first()
    if cmd == "/orders_here":
        if existing:
            call("sendMessage", chat_id=chat["id"], text="Этот чат уже получает заказы Bonch Burgers ✅")
            return
        db.add(TeamChat(company_id=settings.SHOP_COMPANY_ID, chat_id=chat["id"], title=chat.get("title")))
        db.commit()
        call(
            "sendMessage",
            chat_id=chat["id"],
            text="Готово ✅ Новые заказы Bonch Burgers будут приходить сюда с кнопками «Принять», «Готов», «Выдан», «Отменить». "
                 "Отключить: /orders_off",
        )
    else:
        if existing:
            db.delete(existing)
            db.commit()
        call("sendMessage", chat_id=chat["id"], text="Заказы в этот чат больше не отправляются.")


def handle_callback(db, cb: dict) -> None:
    """Order buttons pressed in the kitchen group: ord:<accept|ready|done|cancel>:<order id>."""
    answer = lambda text=None: call("answerCallbackQuery", callback_query_id=cb["id"], **({"text": text} if text else {}))
    data = cb.get("data", "")
    if not data.startswith("ord:"):
        answer()
        return
    try:
        _, action, order_id = data.split(":")
        order = db.query(ShopOrder).filter(ShopOrder.id == int(order_id)).first()
    except ValueError:
        answer()
        return
    chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
    if not order or chat_id not in team_chats(db, order.company_id):
        answer("Нет доступа")
        return
    answer(apply_action(db, order, action) or "Готово")


def process(update: dict) -> None:
    db = SessionLocal()
    try:
        cb = update.get("callback_query")
        if cb:
            handle_callback(db, cb)
            return
        message = update.get("message")
        if not message:
            return
        kind = message.get("chat", {}).get("type")
        if kind == "private":
            reply_start(message)
        elif kind in ("group", "supergroup"):
            handle_group_command(db, message)
    finally:
        db.close()


def main() -> None:
    if not settings.SHOP_BOT_TOKEN:
        # Idle instead of exiting, so `restart: unless-stopped` does not loop until the token is set.
        print("SHOP_BOT_TOKEN is not set, shop_bot is idle.")
        while True:
            time.sleep(3600)

    setup()
    offset = 0
    initial = get_updates(0)
    if initial:
        offset = initial[-1]["update_id"] + 1

    print("Shop bot polling started.")
    last_expire = 0.0
    while True:
        if time.time() - last_expire > 300:
            db = SessionLocal()
            try:
                closed = expire_unpaid(db)
                if closed:
                    print(f"expired {closed} unpaid orders")
            except Exception as exc:
                print(f"expire_unpaid failed: {type(exc).__name__}")
            finally:
                db.close()
            last_expire = time.time()

        try:
            updates = get_updates(offset)
        except Exception as exc:
            print(f"getUpdates failed: {type(exc).__name__}")
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                process(update)
            except Exception as exc:
                print(f"update handling failed: {type(exc).__name__}")


if __name__ == "__main__":
    main()
