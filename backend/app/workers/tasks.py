from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.message import Message
from app.models.task import Task
from app.services.openai_client import client
from app.services.telegram import notify_company


def run_agent_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        agent = (
            db.query(Agent)
            .filter(Agent.id == task.assigned_agent_id)
            .first()
        )
        if not agent:
            task.status = "failed"
            task.error = "Assigned agent not found"
            task.finished_at = datetime.utcnow()
            db.commit()
            return

        task.status = "running"
        task.started_at = datetime.utcnow()
        agent.status = "busy"
        db.commit()

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": agent.system_prompt},
                    {"role": "user", "content": task.instructions},
                ],
            )
            result_text = response.choices[0].message.content or ""

            task.status = "done"
            task.result = result_text
            task.finished_at = datetime.utcnow()
            agent.status = "idle"

            if task.conversation_id:
                db.add(
                    Message(
                        conversation_id=task.conversation_id,
                        sender_type="agent",
                        agent_id=agent.id,
                        content=result_text,
                    )
                )

            db.commit()

            if agent.notify_owner:
                notify_safe(db, task.company_id, f"[{agent.name}] {result_text}")
        except Exception as exc:
            db.rollback()
            task.status = "failed"
            task.error = str(exc)
            task.finished_at = datetime.utcnow()
            agent.status = "idle"
            db.commit()

            if agent.notify_owner:
                notify_safe(db, task.company_id, f"[{agent.name}] Задача завершилась с ошибкой: {exc}")
    finally:
        db.close()


def notify_safe(db, company_id: int, text: str) -> None:
    try:
        notify_company(db, company_id, text)
    except Exception:
        pass
