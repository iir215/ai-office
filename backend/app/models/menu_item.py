from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class MenuItem(BaseModel):
    """One orderable position of a company's menu (prices in UZS)."""

    __tablename__ = "menu_items"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(100),
    )

    name: Mapped[str] = mapped_column(
        String(200),
    )

    name_uz: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    description_uz: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    price: Mapped[int] = mapped_column(
        Integer,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    sort: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # Name of the pixel-art picture in static/shop/sprites/<sprite>.png
    sprite: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )
