from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Task(BaseModel):

    __tablename__ = "tasks"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    director_agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
    )

    assigned_agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
    )

    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=True,
    )

    instructions: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
