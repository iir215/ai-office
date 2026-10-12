from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class MediaAsset(BaseModel):
    """A photo the owner sent to the bot (food truck, premises, dishes...).
    The file lives in static/assets/<company_id>/<filename>."""

    __tablename__ = "media_assets"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        index=True,
    )

    label: Mapped[str] = mapped_column(
        String(255),
    )

    filename: Mapped[str] = mapped_column(
        String(255),
    )
