from sqlalchemy import ForeignKey

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Conversation(BaseModel):

    __tablename__ = "conversations"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )

    director_agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"),
    )
