from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.models.base_model import BaseModel

# awaiting_payment -> new -> accepted -> ready -> done; cancelled/expired from most states.
ORDER_STATUSES = ("awaiting_payment", "new", "accepted", "ready", "done", "cancelled", "expired")


class ShopOrder(BaseModel):
    """An order placed through the Telegram Mini App."""

    __tablename__ = "shop_orders"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        index=True,
    )

    # Human-friendly number, restarts every day (shown on the receipt and to the guest).
    number: Mapped[int] = mapped_column(
        Integer,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
    )

    tg_user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
    )

    tg_username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    customer_name: Mapped[str] = mapped_column(
        String(200),
    )

    phone: Mapped[str] = mapped_column(
        String(40),
    )

    fulfillment: Mapped[str] = mapped_column(
        String(20),  # pickup | delivery
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Delivery point shared from the phone (Telegram location / browser geolocation).
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # JSON list of {"id", "name", "qty", "price"}: names and prices are copied at order time.
    items_json: Mapped[str] = mapped_column(
        Text,
    )

    total: Mapped[int] = mapped_column(
        Integer,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="new",
    )

    payment_method: Mapped[str] = mapped_column(
        String(20),  # cash | click
    )

    payment_status: Mapped[str] = mapped_column(
        String(20),  # unpaid | paid | failed
        default="unpaid",
    )

    click_trans_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    notified_messages: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Guest's Telegram language ("ru" / "uz"): used for messages sent to the guest.
    lang: Mapped[str] = mapped_column(
        String(5),
        default="ru",
    )
