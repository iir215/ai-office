from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel


class EmployeeSighting(BaseModel):

    __tablename__ = "employee_sightings"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
    )

    photo_filename: Mapped[str] = mapped_column(
        String(255),
    )

    comment: Mapped[str] = mapped_column(
        Text,
    )
