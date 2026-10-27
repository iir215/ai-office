"""Reads the POS (YesPOS) notifications that arrive in a dedicated Telegram account and stores them.

STRICTLY READ-ONLY: it never sends, replies, edits, deletes or marks anything as read, and it only
looks at private messages from BOTS (never from people). Use a separate service account: the
session file gives full access to the account it belongs to.

One-time sign-in (you type the phone number and the login code yourself):
    docker compose run --rm -it pos_reader python -m app.pos_reader login
Then the service stores every notification into pos_events. Set POS_READER_SENDER (the bot's
username, without @) once you know which bot is YesPOS, to ignore every other bot.
"""
import asyncio
import os
import sys
import time

from telethon import TelegramClient, events

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.pos_event import PosEvent

SESSION_PATH = "/app/pos_session/reader"


def make_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)


def configured() -> bool:
    return bool(settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH)


async def login() -> None:
    client = make_client()
    await client.start()  # asks for the phone, the code and (if set) the 2FA password in the terminal
    me = await client.get_me()
    print(f"Signed in as id={me.id} username={me.username} (this id goes into YesPOS, Telegram ID field)")
    await client.disconnect()


def store(event) -> None:
    sender = event.sender
    db = SessionLocal()
    try:
        exists = (
            db.query(PosEvent)
            .filter(PosEvent.sender_id == sender.id, PosEvent.tg_message_id == event.id)
            .first()
        )
        if exists:
            return
        db.add(
            PosEvent(
                company_id=settings.SHOP_COMPANY_ID,
                sender_id=sender.id,
                sender_username=sender.username,
                tg_message_id=event.id,
                sent_at=event.date.replace(tzinfo=None),
                text=event.raw_text or "",
            )
        )
        db.commit()
        print(f"stored message {event.id} from @{sender.username}")
    finally:
        db.close()


async def run() -> None:
    client = make_client()
    await client.connect()
    if not await client.is_user_authorized():
        print("pos_reader: not signed in yet; run the one-time login (see the module docstring). Idle.")
        await client.disconnect()
        while True:
            time.sleep(3600)

    me = await client.get_me()
    wanted = settings.POS_READER_SENDER.strip().lstrip("@").lower()
    print(f"pos_reader started as id={me.id}, filter sender={wanted or '(any bot)'}")

    @client.on(events.NewMessage(incoming=True))
    async def on_message(event):
        if not event.is_private:
            return
        sender = await event.get_sender()
        if not getattr(sender, "bot", False):
            return  # never read people's messages
        if wanted and (sender.username or "").lower() != wanted:
            return
        try:
            store(event)
        except Exception as exc:
            print(f"store failed: {type(exc).__name__}")

    await client.run_until_disconnected()


def main() -> None:
    if not configured():
        print("TELEGRAM_API_ID / TELEGRAM_API_HASH are not set, pos_reader is idle.")
        while True:
            time.sleep(3600)
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    asyncio.run(login() if len(sys.argv) > 1 and sys.argv[1] == "login" else run())


if __name__ == "__main__":
    main()
