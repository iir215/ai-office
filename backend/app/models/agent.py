from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Agent(BaseModel):

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_agents_company_name"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    role_type: Mapped[str] = mapped_column(
        String(50),
    )

    system_prompt: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="idle",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    notify_owner: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    is_security_auditor: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    can_publish_instagram: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    handles_instagram_support: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
