from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Message(BaseModel):

    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"),
    )

    sender_type: Mapped[str] = mapped_column(
        String(50),
    )

    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agents.id"),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
    )
