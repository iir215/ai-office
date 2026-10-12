import json
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import Agent
from app.models.message import Message
from app.models.task import Task
from app.services.openai_client import client
from app.services.telegram import notify_company
from app.services.web_search import web_search

MAX_TOOL_ROUNDS = 5

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, trends, or news relevant to the task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _run_completion_with_tools(system_prompt: str, instructions: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instructions},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
        )

        choice = response.choices[0]
        tool_calls = choice.message.tool_calls

        if not tool_calls:
            return choice.message.content or ""

        messages.append(choice.message)

        for tool_call in tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")

            if tool_call.function.name == "web_search":
                result = web_search(args.get("query", ""))
            else:
                result = f"Unknown tool: {tool_call.function.name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return (
        "I looked into this but couldn't finish within the allowed "
        "number of steps. Please try rephrasing the task."
    )


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
            result_text = _run_completion_with_tools(agent.system_prompt, task.instructions)

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

            if agent.notify_owner or task.conversation_id:
                notify_safe(db, task.company_id, f"[{agent.name}] {result_text}")
        except Exception as exc:
            db.rollback()
            task.status = "failed"
            task.error = str(exc)
            task.finished_at = datetime.utcnow()
            agent.status = "idle"
            db.commit()

            if agent.notify_owner or task.conversation_id:
                notify_safe(db, task.company_id, f"[{agent.name}] Задача завершилась с ошибкой: {exc}")
    finally:
        db.close()


def notify_safe(db, company_id: int, text: str) -> None:
    try:
        notify_company(db, company_id, text)
    except Exception:
        pass
