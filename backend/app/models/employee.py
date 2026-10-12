from sqlalchemy import ForeignKey
from sqlalchemy import String

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class Employee(BaseModel):

    __tablename__ = "employees"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
    )

    role: Mapped[str] = mapped_column(
        String(255),
    )

    photo_filename: Mapped[str] = mapped_column(
        String(255),
    )
