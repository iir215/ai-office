from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Camera(BaseModel):

    __tablename__ = "cameras"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )
