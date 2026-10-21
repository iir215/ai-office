"""Customer-facing Telegram bot: greets the guest and opens the ordering Mini App.

It is a separate bot from the internal AION one (create it in @BotFather, put its token
into SHOP_BOT_TOKEN). Order notifications to the team are sent by the AION bot; this bot
only talks to guests (greeting, order status updates).
"""
import time

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.shop import expire_unpaid

API_URL = f"https://api.telegram.org/bot{settings.SHOP_BOT_TOKEN}"

HELLO = {
    "ru": "Добро пожаловать в Bonch Burgers! 🍔\nВыбирайте блюда, оплачивайте онлайн и забирайте у фудтрака или заказывайте доставку.",
    "uz": "Bonch Burgers’ga xush kelibsiz! 🍔\nTaomlarni tanlang, onlayn to‘lang va foodtruckdan olib keting yoki yetkazib berishni buyurtma qiling.",
}
BUTTON = {"ru": "🍔 Открыть меню", "uz": "🍔 Menyuni ochish"}


def app_url() -> str:
    return f"{settings.PUBLIC_BASE_URL}/ui/shop/?c={settings.SHOP_COMPANY_ID}"


def call(method: str, **payload) -> dict | None:
    try:
        resp = httpx.post(f"{API_URL}/{method}", json=payload, timeout=35)
        return resp.json()
    except Exception as exc:
        print(f"{method} failed: {type(exc).__name__}")
        return None


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
            message = update.get("message")
            if message and message.get("chat", {}).get("type") == "private":
                reply_start(message)


if __name__ == "__main__":
    main()
