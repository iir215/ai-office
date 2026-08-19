from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Invite(BaseModel):

    __tablename__ = "invites"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"),
    )

    telegram_username: Mapped[str] = mapped_column(
        String(255),
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )
