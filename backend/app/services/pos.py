"""Hook points for the cash register / receipt printer.

The shop calls get_pos(company_id).push_order(order) when an order becomes ready for
the kitchen (cash order placed, or an online payment confirmed). Nothing is connected
yet: YesPOS has no public API and the receipt printer's model and connection are still
unknown. When they are, add an adapter here (e.g. a print-job queue polled by a small
agent next to the printer, or the POS vendor's API) and return it from get_pos().
"""
from app.models.shop_order import ShopOrder


class PosAdapter:
    name = "none"

    def push_order(self, order: ShopOrder) -> None:
        raise NotImplementedError


class NullPos(PosAdapter):
    name = "none"

    def push_order(self, order: ShopOrder) -> None:
        return None


def get_pos(company_id: int) -> PosAdapter:
    return NullPos()
