from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class InstagramInteractionState(BaseModel):

    __tablename__ = "instagram_interaction_states"
    __table_args__ = (
        UniqueConstraint("kind", "external_id", name="uq_instagram_interaction_kind_external_id"),
    )

    kind: Mapped[str] = mapped_column(
        String(20),
    )

    external_id: Mapped[str] = mapped_column(
        String(512),
    )

    last_value: Mapped[str] = mapped_column(
        String(512),
        nullable=True,
    )
