from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class AllowedEmail(BaseModel):

    __tablename__ = "allowed_emails"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )

    added_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
