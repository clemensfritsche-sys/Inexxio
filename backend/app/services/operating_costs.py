"""Betriebskosten – **tatsächliche** Zahlen für den laufenden Monat (Monat-bis-heute).

Statt einer reinen Schätzung werden die real messbaren Kosten aus dem System gezogen:

* **KI** – aus dem Event-Strom (``ai.chat``/``ai.document_written`` tragen die verbrauchten
  Input-/Output-Tokens je Modell) × Modell-Listenpreis → echte KI-Kosten des Monats.
* **Zahlungen** – Stripe-Gebühren aus den in diesem Monat **bezahlten** Verkäufen
  (≈ 2.9 % + 0.30 CHF je Transaktion auf den Bruttobetrag).
* **Infrastruktur** – Google-Cloud-Grundkosten sind ein weitgehend fixer Monatsbetrag
  (keine per-Objekt-Messung ohne Cloud-Billing-API) → dokumentierte Schätzung, anteilig
  auf die bisherigen Tage des Monats umgelegt.

Alles in CHF. Die KI-Preise sind die (in CHF umgerechneten) Anthropic-Listenpreise pro
1 Mio. Tokens – die **Menge** ist gemessen, der **Preis** ist der Tarif.
"""

import calendar
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Event, Sale
from ..models.base import utcnow

# ─── KI-Modellpreise (CHF pro 1 Mio. Tokens) ─────────────────────────────────────
# Anthropic-Listenpreise (USD) ≈ ×0.88 → CHF. Nach Modellfamilie (Substring im Modell-ID).
_MODEL_PRICES = {
    "opus":  (13.20, 66.00),   # Input, Output  (Opus: $15 / $75)
    "haiku": (0.88, 4.40),     # Haiku 4.5: $1 / $5
    "sonnet": (2.64, 13.20),   # Sonnet: $3 / $15
}
_DEFAULT_PRICE = _MODEL_PRICES["opus"]   # unbekanntes Modell konservativ als Opus rechnen

# Stripe-Standardtarif (CH): 2.9 % + 0.30 CHF je erfolgreicher Transaktion.
_STRIPE_PCT = Decimal("0.029")
_STRIPE_FIXED = Decimal("0.30")

# Infrastruktur-Grundkosten (Google Cloud) – fixer Monatsrahmen (Mittelwert der Spanne).
_INFRA_ITEMS = [
    ("Cloud Run · Backend-API", 12.0),
    ("Cloud SQL · PostgreSQL", 18.0),
    ("Firebase Hosting · Website/Shop", 2.0),
    ("Cloud Storage · Bilder/Dokumente", 1.0),
    ("Secret Manager · Schlüssel", 0.0),
]
_INFRA_MONTHLY = round(sum(v for _, v in _INFRA_ITEMS), 2)


def _price_for(model: str | None) -> tuple[float, float]:
    m = (model or "").lower()
    for key, price in _MODEL_PRICES.items():
        if key in m:
            return price
    return _DEFAULT_PRICE


def _month_window() -> tuple[datetime, int, int]:
    now = utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    return start, now.day, days_in_month


_MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
              "August", "September", "Oktober", "November", "Dezember"]


def _ai_costs(db: Session, start: datetime) -> dict:
    """Tatsächliche KI-Kosten des Monats aus dem Event-Strom (Tokens × Modellpreis)."""
    rows = (
        db.query(Event.payload)
        .filter(Event.event_type.in_(("ai.chat", "ai.document_written")),
                Event.created_at >= start)
        .all()
    )
    total = 0.0
    in_tok = out_tok = 0
    requests = 0
    for (payload,) in rows:
        p = payload or {}
        it = int(p.get("input_tokens") or 0)
        ot = int(p.get("output_tokens") or 0)
        if it == 0 and ot == 0:
            continue
        pin, pout = _price_for(p.get("model"))
        total += it / 1_000_000 * pin + ot / 1_000_000 * pout
        in_tok += it
        out_tok += ot
        requests += 1
    return {"total": round(total, 2), "input_tokens": in_tok,
            "output_tokens": out_tok, "requests": requests}


def _stripe_fees(db: Session, start: datetime) -> dict:
    """Stripe-Gebühren des Monats aus den bezahlten (Stripe-)Verkäufen."""
    sales = (
        db.query(Sale)
        .filter(Sale.is_active == True, Sale.kind == "sale", Sale.status == "paid",
                Sale.paid_at >= start, Sale.payment_method == "stripe")
        .all()
    )
    fees = Decimal("0")
    volume = Decimal("0")
    for s in sales:
        net = s.order_total or Decimal("0")
        gross = net * (Decimal("1") + (s.vat_rate or Decimal("0")) / Decimal("100"))
        fees += gross * _STRIPE_PCT + _STRIPE_FIXED
        volume += gross
    return {"total": round(float(fees), 2), "transactions": len(sales),
            "volume": round(float(volume), 2)}


def operating_costs(db: Session) -> dict:
    """Betriebskosten Monat-bis-heute (tatsächlich, wo messbar) + Monats-Hochrechnung."""
    start, day, days_in_month = _month_window()
    now = utcnow()

    ai = _ai_costs(db, start)
    pay = _stripe_fees(db, start)
    infra_mtd = round(_INFRA_MONTHLY * day / days_in_month, 2)

    groups = [
        {
            "key": "ai", "label": "Künstliche Intelligenz", "basis": "actual",
            "total_chf": ai["total"],
            "items": [
                {"label": "Claude · Chat & Schreibhilfe",
                 "value_chf": ai["total"],
                 "hint": f"{ai['requests']} Anfragen · "
                         f"{(ai['input_tokens'] + ai['output_tokens']) / 1000:.0f}k Tokens"},
            ],
        },
        {
            "key": "payments", "label": "Zahlungen · Stripe", "basis": "actual",
            "total_chf": pay["total"],
            "items": [
                {"label": "Transaktionsgebühren",
                 "value_chf": pay["total"],
                 "hint": f"{pay['transactions']} Zahlungen · Umsatz {pay['volume']:.0f} CHF · 2.9 % + 0.30 CHF"},
            ],
        },
        {
            "key": "infrastructure", "label": "Infrastruktur · Google Cloud", "basis": "estimate",
            "total_chf": infra_mtd,
            "items": [
                {"label": name, "value_chf": round(val * day / days_in_month, 2),
                 "hint": f"≈ {val:.0f} CHF/Mt"}
                for name, val in _INFRA_ITEMS if val > 0
            ],
        },
    ]

    total_mtd = round(ai["total"] + pay["total"] + infra_mtd, 2)
    # Hochrechnung aufs Monatsende: gemessene Kosten linear extrapoliert + volle Infra-Fixkosten.
    measured = ai["total"] + pay["total"]
    projected = round(measured * days_in_month / max(day, 1) + _INFRA_MONTHLY, 2)

    return {
        "period_label": f"{_MONTHS_DE[now.month]} {now.year}",
        "day_of_month": day,
        "days_in_month": days_in_month,
        "groups": groups,
        "total_mtd_chf": total_mtd,
        "projected_month_chf": projected,
    }
