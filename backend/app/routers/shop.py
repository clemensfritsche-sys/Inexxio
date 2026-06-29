"""Öffentlicher Shop (Kunde): Produkt-Listing/-Detail, Checkout, Zahlung.

Listing/Detail sind öffentlich (eingeloggte Kunden sehen zusätzlich ihre privaten
Produkte). Checkout/Zahlung erfordern Login (kein Gast-Checkout).
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, get_optional_user
from ..core.database import get_db
from ..models import Article, CompanySettings, Order, Sale, UserProfile
from ..schemas.shop import (
    PaymentSimulate, ShopCheckout, ShopCheckoutResult, ShopProduct,
)
from ..services import sales as sales_svc
from ..services.payments import get_provider, provider_name

router = APIRouter(prefix="/api/v1/shop", tags=["shop"])


def _lang(request: Request, lang: str | None) -> str:
    if lang in ("de", "en"):
        return lang
    header = request.headers.get("accept-language", "")
    tag = header.split(",")[0].split(";")[0].split("-")[0].lower().strip()
    return tag if tag in ("de", "en") else "de"


@router.get("/config")
async def shop_config(db: Session = Depends(get_db)):
    """Öffentliche Shop-Konfiguration für den Frontend-Währungsumschalter."""
    s = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    return {
        "currencies": sales_svc.shop_currencies(db),
        "default_currency": (s.shop_default_currency if s else None) or "CHF",
    }


@router.get("/products", response_model=list[ShopProduct])
async def list_products(
    request: Request,
    currency: str | None = Query(None),
    country: str | None = Query(None),
    lang: str | None = Query(None),
    db: Session = Depends(get_db),
    user: UserProfile | None = Depends(get_optional_user),
):
    cur = sales_svc.resolve_currency(db, currency, country)
    return [ShopProduct(**p) for p in
            sales_svc.list_products(db, user, cur, country, _lang(request, lang))]


@router.get("/products/{object_id}", response_model=ShopProduct)
async def get_product(
    object_id: int,
    request: Request,
    currency: str | None = Query(None),
    country: str | None = Query(None),
    lang: str | None = Query(None),
    db: Session = Depends(get_db),
    user: UserProfile | None = Depends(get_optional_user),
):
    article = db.query(Article).filter(Article.object_id == object_id, Article.is_active == True).first()
    if not article:
        raise HTTPException(404, detail="Produkt nicht gefunden")
    article = sales_svc.canonical(db, article)   # Ersetzen-Kette: kanonisch zum aktuellen Artikel
    if not sales_svc.can_view(db, article, user):
        raise HTTPException(404, detail="Produkt nicht gefunden")
    cur = sales_svc.resolve_currency(db, currency, country)
    return ShopProduct(**sales_svc.to_product(db, article, cur, country, user, _lang(request, lang)))


@router.post("/checkout", response_model=ShopCheckoutResult)
async def checkout(
    data: ShopCheckout,
    db: Session = Depends(get_db),
    # Login-Pflicht (kein Gast-Checkout – bewusst NICHT gebaut). Ein eingeloggter
    # Kunde (Firebase Magic Link) ist immer der Käufer.
    user: UserProfile = Depends(get_current_user),
):
    article = db.query(Article).filter(
        Article.object_id == data.article_object_id, Article.is_active == True).first()
    if not article:
        raise HTTPException(404, detail="Produkt nicht gefunden")
    # Währung wird NICHT mehr gewählt: Stripe Adaptive Pricing zeigt dem Kunden seine
    # Lokalwährung an der Kasse. Basis ist immer CHF.
    order, sale, url, prov = sales_svc.checkout(db, article, data.quantity, "CHF", user)
    return ShopCheckoutResult(
        order_object_id=order.object_id, sale_token=str(order.object_id),
        provider=prov, payment_url=url,
    )


def _resolve_owned_sale(db: Session, token: str, user: UserProfile) -> tuple[Order, Sale]:
    try:
        oid = int(token)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="Ungültiges Zahlungs-Token")
    order = db.query(Order).filter(Order.object_id == oid, Order.is_active == True).first()
    sale = (db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).first()
            if order else None)
    if not order or not sale:
        raise HTTPException(404, detail="Zahlung nicht gefunden")
    if user.role not in ("admin", "employee") and sale.customer_id != user.id:
        raise HTTPException(403, detail="Keine Berechtigung für diese Zahlung")
    return order, sale


@router.get("/payment/{token}")
async def payment_status(token: str, db: Session = Depends(get_db),
                         user: UserProfile = Depends(get_current_user)):
    """Anzeige der Zahlung (für die manuelle Zahl-/Bestätigungsseite)."""
    order, sale = _resolve_owned_sale(db, token, user)
    net = Decimal(sale.order_total or 0)
    vat = Decimal(sale.vat_rate or 0)
    gross = (net * (Decimal("1") + vat / Decimal("100"))).quantize(Decimal("0.01"))
    return {
        "order_object_id": order.object_id,
        "status": sale.status,
        "currency": sale.currency,
        "net_total": net,
        "vat_rate": vat,
        "gross_total": gross,
        "provider": provider_name(db),
        "paid": sale.status == "paid",
    }


@router.post("/payments/simulate")
async def simulate_payment(data: PaymentSimulate, db: Session = Depends(get_db),
                           user: UserProfile = Depends(get_current_user)):
    """Manueller Provider: Zahlung als Erfolg/Abbruch simulieren (Tests ohne Stripe-Keys)."""
    if provider_name(db) != "manual":
        raise HTTPException(400, detail="Simulation nur im manuellen Modus – mit Stripe über die echte Kasse bezahlen.")
    _resolve_owned_sale(db, data.sale_token, user)   # Ownership prüfen
    provider = get_provider(db)
    sale = provider.handle_webhook(db, b"", None, {"sale_token": data.sale_token, "result": data.result})
    return {"status": sale.status if sale else "unknown"}


@router.get("/session/{session_id}")
async def session_status(session_id: str, db: Session = Depends(get_db),
                         user: UserProfile = Depends(get_current_user)):
    """Status zu einer Stripe-Checkout-Session (für die Erfolgsseite nach Redirect).

    Der Webhook setzt den Verkauf asynchron auf ``paid`` – kurz nach dem Redirect kann der
    Status noch ``requested`` sein («wird verarbeitet»)."""
    order = db.query(Order).filter(Order.stripe_checkout_session_id == session_id).first()
    if not order:
        raise HTTPException(404, detail="Bestellung nicht gefunden")
    sale = db.query(Sale).filter(Sale.order_id == order.id, Sale.is_active == True).first()
    if user.role not in ("admin", "employee") and (not sale or sale.customer_id != user.id):
        raise HTTPException(403, detail="Keine Berechtigung")
    return {
        "order_object_id": order.object_id,
        "status": sale.status if sale else "requested",
        "paid": bool(sale and sale.status == "paid"),
    }


@router.post("/portal")
async def customer_portal(request: Request, db: Session = Depends(get_db),
                          user: UserProfile = Depends(get_current_user)):
    """Stripe Customer Portal (Abo/Zahlungsmittel selbst verwalten). Liefert die Portal-URL."""
    from ..core.config import get_settings
    provider = get_provider(db)
    return_url = f"{get_settings().frontend_base_url.rstrip('/')}/konto"
    url = provider.create_portal_session(db, user, return_url)
    if not url:
        raise HTTPException(400, detail="Kundenportal ist im aktuellen Zahlungsmodus nicht verfügbar.")
    return {"url": url}


@router.post("/payments/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    """Provider-Webhook (Stripe: signaturgeprüft). Verarbeitet Zahlung/Abo-Ereignisse."""
    provider = get_provider(db)
    raw = await request.body()
    sig = request.headers.get("stripe-signature")
    payload = None
    if provider_name(db) == "manual":
        try:
            payload = await request.json()
        except Exception:
            payload = None
    sale = provider.handle_webhook(db, raw, sig, payload)
    return {"status": sale.status if sale else "ok"}
