from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class TeamChat(BaseModel):
    """A Telegram group (kitchen/staff) that receives a company's shop orders through the shop bot."""

    __tablename__ = "team_chats"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        index=True,
    )

    # Telegram chat id of the group (negative number).
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
