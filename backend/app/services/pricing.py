"""Preis-Pipeline (deterministisch, jede Stufe optional):

    Basis-CHF → (Vergleichspreis, rein visuell) → Netto-CHF → Währung (Tageskurs,
    schön gerundet) → Steuer → Anzeige.   Beim Kauf wird daraus ein Snapshot.

Wichtig: KEINE Live-Umrechnung des berechneten Betrags pro Request – der **Tageskurs**
(``services/fx.py``) ist innerhalb des Tages konstant und das Ergebnis wird charmant
gerundet, also über den Tag stabil.

TODO(Erweiterung – NICHT bauen): Hier wäre die nächste optionale Stufe ein **PPP-/Zonen-
Multiplikator** (Kaufkraft je Land) zwischen Netto-CHF und Währungs-Umrechnung. Bewusst
weggelassen (Schlankheit).
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..models import Article, ArticlePrice
from . import fx, tax

CENT = Decimal("0.01")


def charm_round(amount: Decimal, currency: str) -> Decimal:
    """Auf „schöne" Beträge runden. CHF: nächste 0.05 (Schweizer Rundung). Andere
    Währungen: auf eine ganze Zahl mit psychologischer ``.90``-Endung."""
    a = Decimal(amount)
    if a <= 0:
        return Decimal("0.00")
    if (currency or "CHF").upper() == "CHF":
        steps = (a / Decimal("0.05")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return (steps * Decimal("0.05")).quantize(CENT)
    whole = a.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if whole < 1:
        whole = Decimal("1")
    return (whole - Decimal("0.10")).quantize(CENT)


def resolve_primary_price(db: Session, article: Article) -> ArticlePrice | None:
    """Der massgebliche Preis eines Artikels: der ``is_primary``-Preis, sonst der
    älteste aktive Preis (oder ``None``, wenn kein Preis gepflegt ist)."""
    prices = (
        db.query(ArticlePrice)
        .filter(ArticlePrice.article_id == article.id, ArticlePrice.is_active == True)
        .order_by(ArticlePrice.is_primary.desc(), ArticlePrice.id)
        .all()
    )
    return prices[0] if prices else None


def _to_currency(amount_chf: Decimal, rate_to_chf: Decimal) -> Decimal:
    """CHF-Betrag in die Zielwährung umrechnen (``rate_to_chf`` = CHF je 1 Einheit)."""
    if rate_to_chf <= 0:
        return amount_chf
    return amount_chf / rate_to_chf


def price_view(db: Session, article: Article, currency: str = "CHF",
               country: str | None = None, customer=None) -> dict | None:
    """Anzeige-Preis eines Artikels: {currency, kind, interval, net, compare_at,
    tax_rate, gross}. ``None``, wenn kein Preis gepflegt ist.

    Alle Beträge sind in ``currency`` (gerundet); ``tax_rate`` ist der MWST-Satz in
    Prozent, ``gross`` der Brutto-Stückpreis. ``customer`` ist für eine spätere
    B2B-/VAT-ID-Logik vorgesehen (im MVP nicht satzrelevant)."""
    price = resolve_primary_price(db, article)
    if not price:
        return None
    cur = (currency or "CHF").upper()
    rate = fx.get_rate(db, cur)
    net = charm_round(_to_currency(Decimal(price.amount_chf), rate), cur)
    compare_at = None
    if price.compare_at_chf is not None and price.compare_at_chf > price.amount_chf:
        compare_at = charm_round(_to_currency(Decimal(price.compare_at_chf), rate), cur)
    has_vat_id = bool(getattr(customer, "vat_number", None)) if customer else False
    is_b2b = bool(getattr(customer, "company_name", None)) if customer else False
    rate_pct = tax.vat_rate(price.tax_class, country, is_b2b, has_vat_id)
    gross = (net * (Decimal("1") + rate_pct / Decimal("100"))).quantize(CENT)
    return {
        "currency": cur,
        "kind": price.kind,
        "interval": price.interval,
        "net": net,
        "compare_at": compare_at,
        "tax_rate": rate_pct,
        "gross": gross,
    }
