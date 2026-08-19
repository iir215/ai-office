import time
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.task import Task
from app.services.openai_client import client
from app.services.telegram import notify_company

MAX_ITEMS = 50
ALERT_MARKER = "ТРЕВОГА"

# In-memory per-company watermark; lost on restart, acceptable for v1
# (a fresh start simply skips whatever happened before it came up).
last_audit_at: dict[int, datetime] = {}


def build_transcript(db, company_id: int, since: datetime) -> str:
    messages = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.company_id == company_id)
        .filter(Message.created_at > since)
        .order_by(Message.created_at.asc())
        .limit(MAX_ITEMS)
        .all()
    )
    tasks = (
        db.query(Task)
        .filter(Task.company_id == company_id)
        .filter(Task.created_at > since)
        .order_by(Task.created_at.asc())
        .limit(MAX_ITEMS)
        .all()
    )

    lines = [f"[сообщение] {m.sender_type} (agent_id={m.agent_id}): {m.content}" for m in messages]
    lines += [
        f"[задача -> agent_id={t.assigned_agent_id}] поручение: {t.instructions} | результат: {t.result or '(в процессе)'}"
        for t in tasks
    ]
    return "\n".join(lines)


def run_audit(db) -> None:
    now = datetime.utcnow()
    companies = db.query(Company).filter(Company.is_active.is_(True)).all()

    for company in companies:
        auditors = (
            db.query(Agent)
            .filter(Agent.company_id == company.id)
            .filter(Agent.is_security_auditor.is_(True))
            .filter(Agent.is_active.is_(True))
            .all()
        )
        if not auditors:
            continue

        since = last_audit_at.get(company.id, now)
        transcript = build_transcript(db, company.id, since)
        last_audit_at[company.id] = now

        if not transcript:
            continue

        for auditor in auditors:
            try:
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": auditor.system_prompt},
                        {
                            "role": "user",
                            "content": (
                                "Вот сообщения и задачи агентов компании с момента прошлой проверки. "
                                "Проверь их на признаки утечки данных, нарушений ИБ или подозрительного "
                                "поведения агентов, включая Director:\n\n" + transcript
                            ),
                        },
                    ],
                )
                verdict = response.choices[0].message.content or ""
            except Exception as exc:
                print(f"security audit failed for company {company.id}: {exc}")
                continue

            first_line = verdict.splitlines()[0].upper() if verdict else ""
            if ALERT_MARKER in first_line:
                try:
                    notify_company(db, company.id, f"🛡️ [{auditor.name}] {verdict}")
                except Exception:
                    pass


def main() -> None:
    if not settings.OPENAI_API_KEY:
        print("OPENAI_API_KEY is not set, security_auditor will not start.")
        return

    interval = settings.SECURITY_AUDIT_INTERVAL_SECONDS
    print(f"Security auditor loop started, interval={interval}s")

    while True:
        db = SessionLocal()
        try:
            run_audit(db)
        except Exception as exc:
            print(f"audit run failed: {exc}")
        finally:
            db.close()
        time.sleep(interval)


if __name__ == "__main__":
    main()
