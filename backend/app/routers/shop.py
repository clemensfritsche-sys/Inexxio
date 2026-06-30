"""Öffentlicher Shop (Kunde): Produkt-Listing/-Detail, Warenkorb-Checkout, Zahlung.

Listing/Detail sind öffentlich (eingeloggte Kunden sehen zusätzlich ihre privaten
Produkte). Checkout/Zahlung erfordern Login (kein Gast-Checkout).
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, get_optional_user
from ..core.database import get_db
from ..models import Article, CheckoutIntent, CompanySettings, UserProfile
from ..schemas.shop import (
    CustomerOrder, PaymentSimulate, ShopCheckout, ShopCheckoutResult, ShopProduct,
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
    """Öffentliche Shop-Konfiguration: Währungen, Zahlungs-Provider und – für die
    eingebettete Stripe-Kasse – der **Publishable Key** (öffentlich, kein Secret)."""
    s = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    return {
        "currencies": sales_svc.shop_currencies(db),
        "default_currency": (s.shop_default_currency if s else None) or "CHF",
        "provider": provider_name(db),
        "stripe_publishable_key": (s.stripe_publishable_key if s else None) or None,
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
    intent, result = sales_svc.checkout(db, data.items, user)
    return ShopCheckoutResult(
        token=str(intent.id),
        provider=result.get("provider") or provider_name(db),
        session_id=result.get("session_id"),
        client_secret=result.get("client_secret"),
        payment_url=result.get("payment_url"),
    )


def _resolve_owned_intent(db: Session, token: str, user: UserProfile) -> CheckoutIntent:
    try:
        iid = int(token)
    except (TypeError, ValueError):
        raise HTTPException(400, detail="Ungültiges Zahlungs-Token")
    intent = db.query(CheckoutIntent).filter(
        CheckoutIntent.id == iid, CheckoutIntent.is_active == True).first()
    if not intent:
        raise HTTPException(404, detail="Checkout nicht gefunden")
    if user.role not in ("admin", "employee") and intent.customer_id != user.id:
        raise HTTPException(403, detail="Keine Berechtigung für diese Zahlung")
    return intent


def _intent_orders(intent: CheckoutIntent) -> list[int]:
    return [l.get("order_id") for l in (intent.lines or []) if l.get("order_id")]


@router.get("/payment/{token}")
async def payment_status(token: str, db: Session = Depends(get_db),
                         user: UserProfile = Depends(get_current_user)):
    """Anzeige der Zahlung (für die manuelle Zahl-/Bestätigungsseite). Token = Intent-id."""
    intent = _resolve_owned_intent(db, token, user)
    gross = Decimal(intent.amount_chf or 0)   # Basis ist brutto (inkl. MWST)
    return {
        "order_object_id": (_intent_orders(intent) or [None])[0],
        "order_object_ids": _intent_orders(intent),
        "status": "paid" if intent.status == "completed" else (
            "cancelled" if intent.status == "cancelled" else "requested"),
        "currency": "CHF",
        "net_total": gross,
        "vat_rate": Decimal("0"),
        "gross_total": gross,
        "provider": provider_name(db),
        "paid": intent.status == "completed",
    }


@router.post("/payments/simulate")
async def simulate_payment(data: PaymentSimulate, db: Session = Depends(get_db),
                           user: UserProfile = Depends(get_current_user)):
    """Manueller Provider: Zahlung als Erfolg/Abbruch simulieren (Tests ohne Stripe-Keys)."""
    if provider_name(db) != "manual":
        raise HTTPException(400, detail="Simulation nur im manuellen Modus – mit Stripe über die echte Kasse bezahlen.")
    _resolve_owned_intent(db, data.sale_token, user)   # Ownership prüfen
    provider = get_provider(db)
    intent = provider.handle_webhook(db, b"", None, {"sale_token": data.sale_token, "result": data.result})
    return {"status": "paid" if (intent and intent.status == "completed") else (
        "cancelled" if (intent and intent.status == "cancelled") else "unknown")}


@router.get("/session/{session_id}")
async def session_status(session_id: str, db: Session = Depends(get_db),
                         user: UserProfile = Depends(get_current_user)):
    """Status zu einer Stripe-Checkout-Session (für die Erfolgsseite). Der Webhook erzeugt/
    finalisiert die Aufträge asynchron – kurz nach der Rückkehr kann der Intent noch
    ``pending`` sein («wird verarbeitet»)."""
    intent = db.query(CheckoutIntent).filter(
        CheckoutIntent.stripe_session_id == session_id).first()
    if not intent:
        raise HTTPException(404, detail="Bestellung nicht gefunden")
    if user.role not in ("admin", "employee") and intent.customer_id != user.id:
        raise HTTPException(403, detail="Keine Berechtigung")
    orders = _intent_orders(intent)
    return {
        "order_object_id": (orders or [None])[0],
        "order_object_ids": orders,
        "status": "paid" if intent.status == "completed" else "requested",
        "paid": intent.status == "completed",
    }


@router.get("/orders", response_model=list[CustomerOrder])
async def my_orders(db: Session = Depends(get_db),
                    user: UserProfile = Depends(get_current_user)):
    """Eigene Bestellungen + Abos (Kunden-Selbstbedienung)."""
    return [CustomerOrder(**o) for o in sales_svc.list_customer_orders(db, user.id)]


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
    intent = provider.handle_webhook(db, raw, sig, payload)
    return {"status": intent.status if intent else "ok"}
