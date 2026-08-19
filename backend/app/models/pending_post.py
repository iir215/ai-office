from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class PendingPost(BaseModel):

    __tablename__ = "pending_posts"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
    )

    instagram_container_id: Mapped[str] = mapped_column(
        String(64),
    )

    image_url: Mapped[str] = mapped_column(
        Text,
    )

    caption: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )

    notified_messages: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
