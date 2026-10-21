from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.shop_order import ShopOrder
from app.services import shop

# Public router: the Mini App talks to it directly. Guests are identified by Telegram's
# signed initData (orders) or by a per-order token (following one order); Click calls the
# payment endpoints with its own request signature.
router = APIRouter(prefix="/shop", tags=["Shop"])


def _raise(exc: shop.ShopError):
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/app")
def app_data(company_id: int | None = None, db: Session = Depends(get_db)):
    company_id = company_id or settings.SHOP_COMPANY_ID
    try:
        shop.expire_unpaid(db)
        return {"config": shop.get_config(db, company_id), "menu": shop.get_menu(db, company_id)}
    except shop.ShopError as exc:
        _raise(exc)


@router.post("/orders")
def create_order(
    payload: dict,
    company_id: int | None = None,
    x_telegram_init_data: str = Header(default=""),
    db: Session = Depends(get_db),
):
    company_id = company_id or settings.SHOP_COMPANY_ID
    try:
        user = shop.validate_init_data(x_telegram_init_data)
        shop.get_config(db, company_id)
        order = shop.create_order(db, company_id, user, payload)
    except shop.ShopError as exc:
        _raise(exc)
    out = {"order": shop.order_public(order)}
    if order.status == "awaiting_payment":
        out["pay_url"] = shop.pay_url(order)
    return out


@router.get("/orders/{order_id}")
def order_status(order_id: int, t: str = "", db: Session = Depends(get_db)):
    order = db.query(ShopOrder).filter(ShopOrder.id == order_id).first()
    if not order or t != shop.order_token(order.id):
        raise HTTPException(status_code=404, detail="Order not found")
    out = {"order": shop.order_public(order)}
    if order.status == "awaiting_payment":
        out["pay_url"] = shop.pay_url(order)
    return out


@router.post("/payments/click/prepare")
async def click_prepare(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    return shop.click_prepare(db, form)


@router.post("/payments/click/complete")
async def click_complete(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    return shop.click_complete(db, form)
