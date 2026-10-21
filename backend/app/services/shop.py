import hashlib
import hmac
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company
from app.models.menu_item import MenuItem
from app.models.shop_order import ShopOrder
from app.models.team_chat import TeamChat
from app.services.pos import get_pos
from app.services.telegram import edit_message, notify_company, send_location

TASHKENT = timezone(timedelta(hours=5))
MAX_QTY = 20
MAX_LINES = 40

FULFILLMENT = ("pickup", "delivery")
PAYMENT = ("cash", "click")

# Delivery terms are not decided yet: the guest is told the operator will confirm the fee.
DELIVERY_NOTE = {
    "ru": "Стоимость доставки уточнит оператор.",
    "uz": "Yetkazib berish narxini operator aytadi.",
}


class ShopError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def today() -> date:
    return datetime.now(TASHKENT).date()


# ------------------------------------------------------------------ Telegram sign-in

def validate_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Validates Telegram Mini App initData (HMAC with the shop bot token) and returns its user."""
    token = settings.SHOP_BOT_TOKEN
    if not token:
        raise ShopError("Ordering is not configured yet", 503)
    pairs = dict(parse_qsl(init_data or "", keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise ShopError("Open the app from Telegram", 401)
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ShopError("Invalid Telegram signature", 401)
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > max_age_seconds:
            raise ShopError("Session expired, reopen the app", 401)
        user = json.loads(pairs["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise ShopError("Invalid Telegram user", 401)
    return user


def order_token(order_id: int) -> str:
    """Unguessable per-order key: lets the guest follow one order without signing in again
    (the Click payment page returns to the browser, where Telegram's initData is not available)."""
    key = (settings.JWT_SECRET_KEY or settings.SHOP_BOT_TOKEN or "dev").encode()
    return hmac.new(key, f"order:{order_id}".encode(), hashlib.sha256).hexdigest()[:20]


# ------------------------------------------------------------------ menu / config

def click_enabled() -> bool:
    return bool(settings.CLICK_SERVICE_ID and settings.CLICK_MERCHANT_ID and settings.CLICK_SECRET_KEY)


def get_config(db: Session, company_id: int) -> dict:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ShopError("Unknown company", 404)
    return {
        "company_id": company.id,
        "name": company.name,
        "logo": f"/ui/logos/{company.id}.png",
        "click_enabled": click_enabled(),
        "delivery_note": DELIVERY_NOTE,
    }


def get_menu(db: Session, company_id: int) -> list[dict]:
    items = (
        db.query(MenuItem)
        .filter(MenuItem.company_id == company_id, MenuItem.is_active.is_(True))
        .order_by(MenuItem.sort, MenuItem.id)
        .all()
    )
    categories: dict[str, list[dict]] = {}
    for it in items:
        categories.setdefault(it.category, []).append(
            {
                "id": it.id,
                "name": it.name,
                "name_uz": it.name_uz or it.name,
                "description": it.description or "",
                "description_uz": it.description_uz or it.description or "",
                "sprite": it.sprite or "",
                "price": it.price,
            }
        )
    return [{"category": c, "items": v} for c, v in categories.items()]


# ------------------------------------------------------------------ orders

def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        raise ShopError("Enter the phone as +998 XX XXX XX XX")
    return "+" + digits


def create_order(db: Session, company_id: int, user: dict, data: dict) -> ShopOrder:
    fulfillment = data.get("fulfillment")
    if fulfillment not in FULFILLMENT:
        raise ShopError("Choose pickup or delivery")
    payment = data.get("payment_method")
    if payment not in PAYMENT:
        raise ShopError("Choose a payment method")
    if payment == "click" and not click_enabled():
        raise ShopError("Online payment is not available yet", 400)

    name = (data.get("name") or "").strip()[:200]
    if not name:
        raise ShopError("Enter your name")
    phone = normalize_phone(data.get("phone", ""))
    address = (data.get("address") or "").strip()[:500]
    latitude = longitude = None
    loc = data.get("location")
    if loc and fulfillment == "delivery":
        try:
            latitude, longitude = float(loc["lat"]), float(loc["lon"])
        except (KeyError, ValueError, TypeError):
            raise ShopError("Invalid location")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ShopError("Invalid location")
    if fulfillment == "delivery" and not address and latitude is None:
        raise ShopError("Enter the delivery address or share your location")
    comment = (data.get("comment") or "").strip()[:500]

    raw_items = data.get("items") or []
    if not raw_items or len(raw_items) > MAX_LINES:
        raise ShopError("The cart is empty")
    wanted: dict[int, int] = {}
    for line in raw_items:
        try:
            item_id, qty = int(line["id"]), int(line["qty"])
        except (KeyError, ValueError, TypeError):
            raise ShopError("Invalid cart")
        if not 1 <= qty <= MAX_QTY:
            raise ShopError(f"Quantity must be between 1 and {MAX_QTY}")
        wanted[item_id] = wanted.get(item_id, 0) + qty

    menu = {
        m.id: m
        for m in db.query(MenuItem)
        .filter(MenuItem.company_id == company_id, MenuItem.is_active.is_(True), MenuItem.id.in_(list(wanted)))
        .all()
    }
    if len(menu) != len(wanted):
        raise ShopError("Some items are no longer available, refresh the menu")

    lines = [
        {"id": i, "name": menu[i].name, "name_uz": menu[i].name_uz or menu[i].name, "qty": q, "price": menu[i].price}
        for i, q in wanted.items()
    ]
    total = sum(l["qty"] * l["price"] for l in lines)

    day = today()
    number = (
        db.query(func.coalesce(func.max(ShopOrder.number), 0))
        .filter(ShopOrder.company_id == company_id, ShopOrder.order_date == day)
        .scalar()
        or 0
    ) + 1

    lang = "uz" if str(user.get("language_code", "")).lower().startswith("uz") else "ru"
    order = ShopOrder(
        company_id=company_id,
        number=number,
        order_date=day,
        tg_user_id=int(user["id"]),
        tg_username=user.get("username"),
        customer_name=name,
        phone=phone,
        fulfillment=fulfillment,
        address=address or None,
        latitude=latitude,
        longitude=longitude,
        comment=comment or None,
        items_json=json.dumps(lines, ensure_ascii=False),
        total=total,
        status="awaiting_payment" if payment == "click" else "new",
        payment_method=payment,
        payment_status="unpaid",
        lang=lang,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if order.status == "new":
        order_ready_for_kitchen(db, order)
    return order


def order_public(order: ShopOrder) -> dict:
    return {
        "id": order.id,
        "number": order.number,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "fulfillment": order.fulfillment,
        "has_location": order.latitude is not None,
        "total": order.total,
        "items": json.loads(order.items_json),
        "token": order_token(order.id),
    }


def pay_url(order: ShopOrder) -> str:
    params = {
        "service_id": settings.CLICK_SERVICE_ID,
        "merchant_id": settings.CLICK_MERCHANT_ID,
        "amount": f"{order.total:.2f}",  # Click expects N.NN
        "transaction_param": order.id,
        "return_url": f"{settings.PUBLIC_BASE_URL}/ui/shop/?c={order.company_id}&o={order.id}&t={order_token(order.id)}",
    }
    if settings.CLICK_MERCHANT_USER_ID:
        params["merchant_user_id"] = settings.CLICK_MERCHANT_USER_ID
    return "https://my.click.uz/services/pay?" + urlencode(params)


# ------------------------------------------------------------------ team + guest messages

def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " сум"


def team_text(order: ShopOrder) -> str:
    lines = json.loads(order.items_json)
    kind = "самовывоз" if order.fulfillment == "pickup" else "доставка"
    pay = (
        "Click — оплачено ✅" if order.payment_method == "click" and order.payment_status == "paid"
        else "Click — ждём оплату" if order.payment_method == "click"
        else "наличными при получении"
    )
    state = {
        "awaiting_payment": "⏳ ждёт оплату", "new": "🆕 новый", "accepted": "✅ принят",
        "ready": "🍔 готов", "done": "✔️ выдан", "cancelled": "❌ отменён", "expired": "⌛ не оплачен",
    }.get(order.status, order.status)
    out = [f"🧾 Заказ №{order.number} — {kind} · {state}", f"{order.customer_name}, {order.phone}"]
    if order.tg_username:
        out[-1] += f" (@{order.tg_username})"
    if order.address:
        out.append(f"Адрес: {order.address}")
    if order.latitude is not None:
        out.append(f"📍 Локация гостя: https://www.google.com/maps?q={order.latitude:.6f},{order.longitude:.6f}")
    if order.fulfillment == "delivery":
        out.append("Доставка: стоимость уточнить с гостем")
    out.append("")
    out += [f"• {l['name']} ×{l['qty']} — {money(l['qty'] * l['price'])}" for l in lines]
    out.append("")
    out.append(f"Итого: {money(order.total)}")
    out.append(f"Оплата: {pay}")
    if order.comment:
        out.append(f"Комментарий: {order.comment}")
    return "\n".join(out)


def team_keyboard(order: ShopOrder) -> dict:
    def btn(text: str, action: str) -> dict:
        return {"text": text, "callback_data": f"ord:{action}:{order.id}"}

    if order.status == "new":
        row = [btn("✅ Принять", "accept"), btn("❌ Отменить", "cancel")]
    elif order.status == "accepted":
        row = [btn("🍔 Готов", "ready"), btn("❌ Отменить", "cancel")]
    elif order.status == "ready":
        row = [btn("✔️ Выдан", "done")]
    else:
        return {"inline_keyboard": []}
    return {"inline_keyboard": [row]}


GUEST_TEXT = {
    "accepted": {
        "ru": "Заказ №{n} принят и готовится 🍔",
        "uz": "№{n}-buyurtma qabul qilindi va tayyorlanmoqda 🍔",
    },
    "ready_pickup": {
        "ru": "Заказ №{n} готов! Заберите его у фудтрака 🎉",
        "uz": "№{n}-buyurtma tayyor! Uni foodtruckdan olib keting 🎉",
    },
    "ready_delivery": {
        "ru": "Заказ №{n} готов и передан на доставку 🚚",
        "uz": "№{n}-buyurtma tayyor va yetkazib berishga topshirildi 🚚",
    },
    "done": {
        "ru": "Приятного аппетита! Заказ №{n} выдан. Спасибо, что выбрали Bonch Burgers 💛",
        "uz": "Yoqimli ishtaha! №{n}-buyurtma topshirildi. Bonch Burgers’ni tanlaganingiz uchun rahmat 💛",
    },
    "cancelled": {
        "ru": "К сожалению, заказ №{n} отменён. Если вы платили онлайн, мы вернём деньги.",
        "uz": "Afsuski, №{n}-buyurtma bekor qilindi. Onlayn to‘lagan bo‘lsangiz, pulni qaytaramiz.",
    },
    "paid": {
        "ru": "Оплата заказа №{n} получена, передаём на кухню ✅",
        "uz": "№{n}-buyurtma uchun to‘lov qabul qilindi, oshxonaga yubordik ✅",
    },
    "new": {
        "ru": "Заказ №{n} оформлен. Мы скоро его подтвердим.",
        "uz": "№{n}-buyurtma rasmiylashtirildi. Tez orada tasdiqlaymiz.",
    },
}


def tg_api(token: str, method: str, **payload) -> dict | None:
    """Telegram Bot API call. Only the exception type is logged: the URL contains the token."""
    try:
        return httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=15).json()
    except Exception as exc:
        print(f"telegram {method} failed: {type(exc).__name__}")
        return None


def notify_guest(order: ShopOrder, key: str) -> None:
    if not settings.SHOP_BOT_TOKEN:
        return
    texts = GUEST_TEXT.get(key)
    if not texts:
        return
    text = texts.get(order.lang, texts["ru"]).format(n=order.number)
    tg_api(settings.SHOP_BOT_TOKEN, "sendMessage", chat_id=order.tg_user_id, text=text)


def team_chats(db: Session, company_id: int) -> list[int]:
    return [c.chat_id for c in db.query(TeamChat).filter(TeamChat.company_id == company_id).all()]


def send_to_team(db: Session, company_id: int, text: str, reply_markup: dict | None = None) -> list[dict]:
    """Groups registered with the shop bot (/orders_here) get the message through the shop bot.
    With no group registered, or if every send fails, it falls back to the AION company chats,
    so an order never goes unseen. Each result records which bot sent it (needed to edit it later)."""
    sent: list[dict] = []
    if settings.SHOP_BOT_TOKEN:
        for chat_id in team_chats(db, company_id):
            payload = {"chat_id": chat_id, "text": text}
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            res = tg_api(settings.SHOP_BOT_TOKEN, "sendMessage", **payload)
            if res and res.get("ok"):
                sent.append({"chat_id": str(chat_id), "message_id": res["result"]["message_id"], "bot": "shop"})
    if not sent:
        sent = [{**m, "bot": "aion"} for m in notify_company(db, company_id, text, reply_markup)]
    return sent


def order_ready_for_kitchen(db: Session, order: ShopOrder) -> None:
    """Cash order placed, or Click payment confirmed: tell the team and the POS hook."""
    try:
        sent = send_to_team(db, order.company_id, team_text(order), team_keyboard(order))
        order.notified_messages = json.dumps(sent)
        db.commit()
        if order.latitude is not None:
            for m in sent:
                try:
                    if m.get("bot") == "shop":
                        tg_api(settings.SHOP_BOT_TOKEN, "sendLocation", chat_id=m["chat_id"], latitude=order.latitude,
                               longitude=order.longitude, reply_to_message_id=m["message_id"])
                    else:
                        send_location(m["chat_id"], order.latitude, order.longitude, reply_to=m["message_id"])
                except Exception as exc:
                    print(f"send_location failed for order {order.id}: {type(exc).__name__}")
    except Exception as exc:
        print(f"team notification failed for order {order.id}: {type(exc).__name__}")
    try:
        get_pos(order.company_id).push_order(order)
    except Exception as exc:
        print(f"POS hook failed for order {order.id}: {exc!r}")
    notify_guest(order, "new" if order.payment_method == "cash" else "paid")


def refresh_team_messages(order: ShopOrder) -> None:
    for m in json.loads(order.notified_messages or "[]"):
        try:
            if m.get("bot") == "shop":
                tg_api(settings.SHOP_BOT_TOKEN, "editMessageText", chat_id=m["chat_id"], message_id=m["message_id"],
                       text=team_text(order), reply_markup=team_keyboard(order))
            else:
                edit_message(m["chat_id"], m["message_id"], team_text(order), team_keyboard(order))
        except Exception:
            pass


TRANSITIONS = {
    "accept": ({"new"}, "accepted"),
    "ready": ({"new", "accepted"}, "ready"),
    "done": ({"ready", "accepted"}, "done"),
    "cancel": ({"new", "accepted", "ready", "awaiting_payment"}, "cancelled"),
}


def apply_action(db: Session, order: ShopOrder, action: str) -> str | None:
    """Moves the order along (called from the team's Telegram buttons). Returns an error text or None."""
    if action not in TRANSITIONS:
        return "Неизвестное действие"
    allowed_from, new_status = TRANSITIONS[action]
    if order.status not in allowed_from:
        return "Статус заказа уже изменён"
    order.status = new_status
    db.commit()
    refresh_team_messages(order)

    if new_status == "accepted":
        notify_guest(order, "accepted")
    elif new_status == "ready":
        notify_guest(order, "ready_pickup" if order.fulfillment == "pickup" else "ready_delivery")
    elif new_status == "done":
        notify_guest(order, "done")
    elif new_status == "cancelled":
        notify_guest(order, "cancelled")
        if order.payment_method == "click" and order.payment_status == "paid":
            try:
                send_to_team(db, order.company_id, f"💸 Заказ №{order.number} отменён после оплаты Click: верните {money(order.total)} в кабинете Click.")
            except Exception:
                pass
    return None


# ------------------------------------------------------------------ Click Shop API

def _md5(*parts) -> str:
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()


def _click_reply(form: dict, error: int, note: str, **extra) -> dict:
    out = {
        "click_trans_id": form.get("click_trans_id"),
        "merchant_trans_id": form.get("merchant_trans_id"),
        "error": error,
        "error_note": note,
    }
    out.update(extra)
    return out


def click_prepare(db: Session, form: dict) -> dict:
    f = {k: (v if v is not None else "") for k, v in form.items()}
    expected = _md5(
        f.get("click_trans_id"), f.get("service_id"), settings.CLICK_SECRET_KEY,
        f.get("merchant_trans_id"), f.get("amount"), f.get("action"), f.get("sign_time"),
    )
    if not click_enabled() or not hmac.compare_digest(expected, str(f.get("sign_string"))):
        return _click_reply(f, -1, "SIGN CHECK FAILED!")
    if str(f.get("action")) != "0":
        return _click_reply(f, -3, "Action not found")
    order = _order_by_trans(db, f.get("merchant_trans_id"))
    if not order:
        return _click_reply(f, -5, "Order not found")
    if order.payment_status == "paid":
        return _click_reply(f, -4, "Already paid")
    if order.status != "awaiting_payment":
        return _click_reply(f, -9, "Transaction cancelled")
    if abs(float(f.get("amount") or 0) - order.total) > 0.01:
        return _click_reply(f, -2, "Incorrect parameter amount")
    order.click_trans_id = str(f.get("click_trans_id"))
    db.commit()
    return _click_reply(f, 0, "Success", merchant_prepare_id=order.id)


def click_complete(db: Session, form: dict) -> dict:
    f = {k: (v if v is not None else "") for k, v in form.items()}
    expected = _md5(
        f.get("click_trans_id"), f.get("service_id"), settings.CLICK_SECRET_KEY,
        f.get("merchant_trans_id"), f.get("merchant_prepare_id"), f.get("amount"),
        f.get("action"), f.get("sign_time"),
    )
    if not click_enabled() or not hmac.compare_digest(expected, str(f.get("sign_string"))):
        return _click_reply(f, -1, "SIGN CHECK FAILED!")
    if str(f.get("action")) != "1":
        return _click_reply(f, -3, "Action not found")
    order = _order_by_trans(db, f.get("merchant_trans_id"))
    if not order:
        return _click_reply(f, -5, "Order not found")
    if str(f.get("merchant_prepare_id")) != str(order.id) or order.click_trans_id != str(f.get("click_trans_id")):
        return _click_reply(f, -6, "Transaction not found")
    if order.payment_status == "paid":
        return _click_reply(f, -4, "Already paid", merchant_confirm_id=order.id)
    if abs(float(f.get("amount") or 0) - order.total) > 0.01:
        return _click_reply(f, -2, "Incorrect parameter amount")
    try:
        click_error = int(f.get("error") or 0)
    except ValueError:
        click_error = -8
    if click_error < 0 or order.status != "awaiting_payment":
        order.payment_status = "failed"
        if order.status == "awaiting_payment":
            order.status = "cancelled"
        db.commit()
        return _click_reply(f, -9, "Transaction cancelled")

    order.payment_status = "paid"
    order.status = "new"
    order.paid_at = datetime.utcnow()
    db.commit()
    order_ready_for_kitchen(db, order)
    return _click_reply(f, 0, "Success", merchant_confirm_id=order.id)


def _order_by_trans(db: Session, merchant_trans_id) -> ShopOrder | None:
    try:
        order_id = int(merchant_trans_id)
    except (TypeError, ValueError):
        return None
    return db.query(ShopOrder).filter(ShopOrder.id == order_id).first()


def expire_unpaid(db: Session, older_than_minutes: int = 30) -> int:
    """Unpaid Click orders that were abandoned: close them so they never reach the kitchen later."""
    cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
    rows = (
        db.query(ShopOrder)
        .filter(ShopOrder.status == "awaiting_payment", ShopOrder.created_at < cutoff)
        .all()
    )
    for o in rows:
        o.status = "expired"
    db.commit()
    return len(rows)
