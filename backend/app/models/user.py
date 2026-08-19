from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class User(BaseModel):

    __tablename__ = "users"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"),
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    telegram_chat_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    company = relationship(
    "Company",
    back_populates="users",
)
    role = relationship(
    "Role",
    back_populates="users",
)