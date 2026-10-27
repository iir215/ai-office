from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class PosEvent(BaseModel):
    """A notification the POS (YesPOS) bot sent to the service Telegram account: shift, receipt,
    stock... Stored raw first; parsing is added once the message formats are known."""

    __tablename__ = "pos_events"
    __table_args__ = (UniqueConstraint("sender_id", "tg_message_id", name="uq_pos_event_message"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        index=True,
    )

    sender_id: Mapped[int] = mapped_column(
        BigInteger,
    )

    sender_username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    tg_message_id: Mapped[int] = mapped_column(
        BigInteger,
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime,
    )

    text: Mapped[str] = mapped_column(
        Text,
    )

    # Filled by the parser later: "shift" | "receipt" | "stock" | "supplier" | None
    kind: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    parsed_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
