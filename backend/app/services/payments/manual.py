"""Manueller Zahlungs-Provider (Default) – **kein externer Call**.

``create_checkout`` liefert eine interne Seite ``/shop/pay/{token}``; dort simuliert der
Kunde Erfolg/Abbruch. ``handle_event`` (ausgelöst von ``POST /shop/payments/simulate``)
setzt den Verkauf auf ``paid`` bzw. ``cancelled``. So ist der gesamte Kauf-/Auftragsfluss
ohne externe Abhängigkeit testbar.

Der ``token`` ist die **Auftrags-Objektnummer** (der Verkauf läuft unter dem Auftrag,
ohne eigene Nummer) – ausreichend als öffentliche, eindeutige Referenz.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...models import Order, Sale
from .. import sale as sale_svc
from .base import PaymentProvider


def sale_token(order: Order) -> str:
    return str(order.object_id)


def _resolve_sale(db: Session, token: str) -> tuple[Order, Sale]:
    try:
        oid = int(token)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="Ungültiges Zahlungs-Token")
    order = db.query(Order).filter(Order.object_id == oid, Order.is_active == True).first()
    if not order:
        raise HTTPException(404, detail="Auftrag zum Zahlungs-Token nicht gefunden")
    sale = db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).first()
    if not sale:
        raise HTTPException(404, detail="Verkauf zum Zahlungs-Token nicht gefunden")
    return order, sale


class ManualProvider(PaymentProvider):
    name = "manual"

    def create_checkout(self, db: Session, order: Order, sale: Sale) -> str:
        base = get_settings().frontend_base_url.rstrip("/")
        return f"{base}/shop/pay?token={sale_token(order)}"

    def handle_event(self, db: Session, payload: dict) -> Sale | None:
        token = payload.get("sale_token")
        result = (payload.get("result") or "").lower()
        _, sale = _resolve_sale(db, str(token))
        if result in ("paid", "success", "succeeded"):
            return sale_svc.mark_paid(db, sale)
        if result in ("cancelled", "canceled", "failed"):
            return sale_svc.mark_cancelled(db, sale)
        raise HTTPException(400, detail="Unbekanntes Zahlungs-Ergebnis (paid|cancelled)")
