from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.db.session import SessionLocal
from app.models.instagram_account import InstagramAccount
from app.services.telegram import notify_company

GRAPH_URL = "https://graph.instagram.com"

# Long-lived tokens live 60 days; refresh well before that, and retry at most
# once a day so a persistent failure alerts daily instead of every poll loop.
REFRESH_AFTER = timedelta(days=30)
REFRESH_RETRY_EVERY = timedelta(hours=24)


class InstagramNotConnected(RuntimeError):
    pass


@dataclass(frozen=True)
class InstagramCreds:
    account_id: str
    token: str
    username: str | None


def get_creds(company_id: int) -> InstagramCreds:
    db = SessionLocal()
    try:
        account = (
            db.query(InstagramAccount)
            .filter(InstagramAccount.company_id == company_id)
            .first()
        )
        if account is None:
            raise InstagramNotConnected(
                f"Instagram не подключён для компании id={company_id}"
            )
        return InstagramCreds(account.account_id, account.access_token, account.username)
    finally:
        db.close()


def has_account(company_id: int) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(InstagramAccount.id)
            .filter(InstagramAccount.company_id == company_id)
            .first()
            is not None
        )
    finally:
        db.close()


def refresh_due_accounts(db) -> None:
    now = datetime.utcnow()
    for account in db.query(InstagramAccount).all():
        if account.token_refreshed_at and now - account.token_refreshed_at < REFRESH_AFTER:
            continue
        if account.last_refresh_attempt_at and now - account.last_refresh_attempt_at < REFRESH_RETRY_EVERY:
            continue

        account.last_refresh_attempt_at = now
        db.commit()

        label = f"@{account.username}" if account.username else f"id={account.account_id}"
        try:
            resp = httpx.get(
                f"{GRAPH_URL}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": account.access_token},
                timeout=20,
            )
            data = resp.json()
            new_token = data.get("access_token")
            if resp.status_code != 200 or not new_token:
                raise RuntimeError(str(data.get("error", data))[:300])
            account.access_token = new_token
            account.token_refreshed_at = now
            try:
                # Keep the handle in sync if the account was renamed; the
                # support loop uses it to recognise the account's own comments.
                me = httpx.get(
                    f"{GRAPH_URL}/me",
                    params={"fields": "username", "access_token": new_token},
                    timeout=20,
                ).json()
                if me.get("username"):
                    account.username = me["username"]
            except Exception as exc:
                print(f"username sync failed for {label}: {exc!r}")
            db.commit()
            print(f"Instagram token refreshed for {label}")
        except Exception as exc:
            print(f"Instagram token refresh failed for {label}: {exc}")
            try:
                notify_company(
                    db,
                    account.company_id,
                    f"⚠️ Не удалось обновить токен Instagram {label}: {exc}\n"
                    "Если это повторится, токен истечёт и публикации/ответы остановятся — "
                    "аккаунт нужно подключить заново.",
                )
            except Exception as notify_exc:
                print(f"notify_company failed: {notify_exc!r}")
