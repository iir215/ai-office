from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class InstagramAccount(BaseModel):

    __tablename__ = "instagram_accounts"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        unique=True,
    )

    account_id: Mapped[str] = mapped_column(
        String(64),
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    access_token: Mapped[str] = mapped_column(
        Text,
    )

    token_refreshed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_refresh_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
