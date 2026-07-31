"""Preis-Pipeline – das automatisierte Herzstück. **Du pflegst NUR den Basispreis in CHF**
(genau eine Zahl je Preis); alles andere wird abgeleitet.

Jeder angezeigte Preis durchläuft dieselbe deterministische Kette; jede Stufe ist
optional/abschaltbar (Default ist schlank: nur Basispreis + Währung + Steuer):

    Basispreis CHF
      ├─① Geltungsbereich:  Kunden-/Gruppenpreis schlägt Standardpreis   (B2B – Extension-Hook)
      ├─② Kaufkraft-Faktor: × Zonen-Multiplikator (nur wenn aktiviert)   (PPP, company_settings)
      ├─③ Rabatt/Aktion:    Vergleichspreis (visuell); Coupons = Extension
      │       ▼ Netto-CHF
      ├─④ Währung:          gepinnter Kurs → „schöne" Rundung (stabil, re-pin bei >3 % Drift)
      │       ▼ Anzeigepreis in Landeswährung
      └─⑤ Steuer:           + MWST nach Lieferland (B2B/B2C, VAT-ID)
              ▼ Anzeige · beim Checkout → SNAPSHOT (eingefroren)

Währung – State of the Art (keine Live-Umrechnung pro Request): der Fremdwährungspreis wird
**gepinnt** (``ArticlePrice.pinned``) und bleibt stabil, bis (a) der CHF-Basispreis sich
ändert oder (b) der Tageskurs um mehr als ``DRIFT_THRESHOLD`` (3 %) wegdriftet – dann re-pinnt
die Pipeline automatisch (lazy, kein Cron). So flackern Preise nicht und bleiben „schön".

Diese gepinnte Pipeline ist die **EINE Kursquelle**: der hier berechnete Betrag wird der
Stripe-Kasse in der Präsentationswährung übergeben (``selling._resolve_line`` →
``stripe_provider._line_item``). Stripe „Adaptive Pricing" ist bewusst **AUS**
(``docs/stripe-setup.md``) – sonst rechnete Stripe mit EIGENEM Kurs um und die Anzeige
(unser Kurs) wiche von der Belastung ab (Anzeige 11.80 ↔ Belastung 11.82).
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import Article, ArticlePrice
from . import fx, tax

CENT = Decimal("0.01")
ONE = Decimal("1")
# Schwelle, ab der ein gepinnter Fremdwährungspreis neu gepinnt wird (Kurs-Drift).
DRIFT_THRESHOLD = Decimal("0.03")


def charm_round(amount: Decimal, currency: str) -> Decimal:
    """Auf „schöne" Beträge runden. CHF: nächste 0.05 (Schweizer Rundung). Andere
    Währungen: auf eine ganze Zahl mit psychologischer ``.90``-Endung (z. B. € 990, nicht € 987.34)."""
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


def price_rank(p: ArticlePrice) -> int:
    """Abos zuerst (Produktabo, dann Nutzungsabo), zuletzt Einmalkauf – EINE Sortier-
    Wahrheit für Shop-Listing (``sales.sort_prices``) und Hauptpreis-Auflösung."""
    if p.kind == "subscription":
        return 0 if p.sub_type == "product" else 1
    return 2


def sort_key(p: ArticlePrice) -> tuple:
    return (price_rank(p), 0 if p.is_primary else 1, p.id)


def resolve_primary_price(db: Session, article: Article) -> ArticlePrice | None:
    """Der massgebliche Preis eines Artikels = die **oberste** Option in der Shop-Reihenfolge
    (Produktabo → Nutzungsabo → Einmalkauf, dann Hauptpreis, dann id). ``None`` ohne Preis."""
    prices = (
        db.query(ArticlePrice)
        .filter(ArticlePrice.article_id == article.id, ArticlePrice.is_active == True)
        .all()
    )
    prices.sort(key=sort_key)
    return prices[0] if prices else None


def resolve_one_time_price(db: Session, article_id: int) -> ArticlePrice | None:
    """Die (bevorzugt primäre) **Einmalkauf**-Preisoption eines Artikels – unabhängig
    davon, ob daneben AUCH ein Abo-Preis existiert. ``resolve_primary_price`` sortiert
    Abos zuerst (Shop-Reihenfolge); ein ERP-Direktverkauf mit mehreren Positionen
    braucht dagegen IMMER den Einmalkauf (Abos lassen sich nicht mengenweise in einem
    Beleg mischen) – deshalb hier gezielt danach gefragt statt über die primäre Option."""
    prices = (
        db.query(ArticlePrice)
        .filter(ArticlePrice.article_id == article_id, ArticlePrice.kind == "one_time",
                ArticlePrice.is_active == True)
        .all()
    )
    prices.sort(key=lambda p: (0 if p.is_primary else 1, p.id))
    return prices[0] if prices else None


def is_subscription_exclusive(db: Session, article_id: int) -> bool:
    """True, wenn der Artikel NUR über ein Abo verkauft werden kann (kein Einmalkauf-Preis
    hinterlegt) – ein solcher Artikel lässt sich nicht mit weiteren Positionen in EINEM
    Verkauf kombinieren (Stripe: ein Checkout ist entweder Einmalkauf oder Abo; im ERP hat
    der Verkaufsschritt keine Möglichkeit, je Position ein anderes Preismodell zu wählen)."""
    if resolve_one_time_price(db, article_id) is not None:
        return False
    return (
        db.query(ArticlePrice.id)
        .filter(ArticlePrice.article_id == article_id, ArticlePrice.kind == "subscription",
                ArticlePrice.is_active == True)
        .first()
        is not None
    )


# ─── Stufe ① Geltungsbereich (Kunden-/Gruppenpreis) – Extension-Hook ──────────────

def _customer_price_override(db: Session, price: ArticlePrice, customer) -> Decimal | None:
    """B2B-Vertrags-/Gruppenpreis (CHF-Basis), der den Standardpreis schlägt.

    TODO(Erweiterung – NICHT gebaut): kunden-/gruppenspezifische Preislisten. Default:
    keine Übersteuerung (``None``) – die Stufe ist abgeschaltet."""
    return None


# ─── Stufe ② Kaufkraft-/Zonen-Faktor (PPP) – optional via company_settings ────────

def _zone_factor(db: Session, country: str | None) -> Decimal:
    """Multiplikator je Land/Zone (PPP). Aktiv nur, wenn in der Systemkonfiguration
    ``pricing_zone_factors`` (Land→Faktor) gepflegt ist – sonst neutral (1.0)."""
    if not country:
        return ONE
    from .sites import find_primary
    s = find_primary(db)          # Preis-Pipeline: Systemkonfiguration am Hauptsitz
    factors = getattr(s, "pricing_zone_factors", None) if s else None
    if not factors:
        return ONE
    raw = factors.get(country) or factors.get(country.upper()) or factors.get(country.lower())
    try:
        return Decimal(str(raw)) if raw else ONE
    except Exception:
        return ONE


def _net_chf(db: Session, price: ArticlePrice, country: str | None, customer) -> Decimal:
    """Netto-CHF nach den Stufen ①②③ (Default = Basispreis unverändert)."""
    base = Decimal(price.amount_chf)
    override = _customer_price_override(db, price, customer)   # ①
    if override is not None:
        base = override
    base = base * _zone_factor(db, country)                    # ②
    # ③ Rabatt: der Vergleichspreis ist rein visuell (kein Netto-Abzug); echte Coupons = Extension.
    return base.quantize(CENT)


# ─── Stufe ④ Währung: gepinnter Kurs + „schöne" Rundung (re-pin bei Drift) ─────────

def _pinned_net(db: Session, price: ArticlePrice, currency: str,
                net_chf: Decimal, rate: Decimal) -> Decimal:
    """Gepinnter Fremdwährungs-Nettopreis – stabil bis Basis-Änderung oder >3 % Kurs-Drift.

    Schreibt den Pin (lazy) bei Bedarf zurück; ``rate`` = CHF je 1 Einheit der Währung."""
    pins = dict(price.pinned or {})
    p = pins.get(currency)
    if p and rate > 0:
        try:
            same_base = Decimal(str(p.get("base"))) == net_chf
            pinned_rate = Decimal(str(p.get("rate")))
            drift = abs(rate - pinned_rate) / pinned_rate if pinned_rate > 0 else ONE
            if same_base and drift <= DRIFT_THRESHOLD:
                return Decimal(str(p.get("net")))   # stabil – kein Re-Pin
        except Exception:
            pass
    net = charm_round(net_chf / rate, currency) if rate > 0 else charm_round(net_chf, currency)
    pins[currency] = {"net": str(net), "rate": str(rate), "base": str(net_chf)}
    price.pinned = pins
    # Pin persistieren – aber NIE fremde, halbfertige Änderungen des Aufrufers mit-committen:
    # der Preis-View ist ein LESE-Pfad. Hat die Session ausser dem Pin noch etwas im Puffer,
    # wird nur geflusht (der Aufrufer schliesst seine Transaktion selbst ab); nur auf den
    # reinen GET-Pfaden (Shop-Listing/Detail, die selbst nie committen) committet der Pin.
    try:
        others = [o for o in (set(db.dirty) | set(db.new) | set(db.deleted)) if o is not price]
        if others:
            db.flush()
        else:
            db.commit()
    except Exception:
        db.rollback()
    return net


def _to_currency_simple(amount_chf: Decimal, currency: str, rate: Decimal) -> Decimal:
    """Einfache (ungepinnte) Umrechnung + Rundung – für rein visuelle Beträge (Vergleichspreis)."""
    if (currency or "CHF").upper() == "CHF":
        return charm_round(amount_chf, "CHF")
    return charm_round(amount_chf / rate, currency) if rate > 0 else charm_round(amount_chf, currency)


# ─── Gesamtansicht ────────────────────────────────────────────────────────────────

def price_view_for(db: Session, price: ArticlePrice, currency: str = "CHF",
                   country: str | None = None, customer=None) -> dict:
    """Anzeige-Preis EINER konkreten Preis-Option: {currency, kind, interval, sub_type,
    net, compare_at, tax_rate, gross}. Alle Beträge in ``currency``."""
    cur = (currency or "CHF").upper()

    net_chf = _net_chf(db, price, country, customer)          # ①②③
    factor = (net_chf / Decimal(price.amount_chf)) if price.amount_chf else ONE

    if cur == "CHF":                                          # ④ Währung
        net = charm_round(net_chf, "CHF")
        rate = ONE
    else:
        rate = fx.get_rate(db, cur)
        net = _pinned_net(db, price, cur, net_chf, rate)      # gepinnt + „schön"

    compare_at = None
    if price.compare_at_chf is not None and price.compare_at_chf > price.amount_chf:
        compare_chf = (Decimal(price.compare_at_chf) * factor).quantize(CENT)
        compare_at = _to_currency_simple(compare_chf, cur, rate)

    has_vat_id = bool(getattr(customer, "vat_number", None)) if customer else False
    is_b2b = bool(getattr(customer, "company_name", None)) if customer else False
    # Steuerklasse ist kein UI-Feld mehr (Stripe Tax übernimmt die finale Steuer); für die
    # CHF-Anzeige gilt der CH-Standardsatz (bzw. die historisch gepflegte Klasse).
    rate_pct = tax.vat_rate(getattr(price, "tax_class", None) or "standard", country, is_b2b, has_vat_id)   # ⑤ Steuer
    # Preisauszeichnung (tax_behavior): brutto/inklusive → der Basispreis IST der Brutto-
    # Endpreis (schöne Zahl), die MWST wird herausgerechnet; netto/exklusive → MWST oben drauf.
    # (Die finale, länderabhängige Steuer rechnet Stripe Tax an der Kasse; dies ist die Anzeige.)
    inclusive = get_settings().prices_tax_inclusive
    factor_pct = ONE + rate_pct / Decimal("100")
    if inclusive:
        gross = net
        net = (gross / factor_pct).quantize(CENT) if factor_pct > 0 else gross
        if compare_at is not None:
            # compare bleibt brutto (Vergleichs-Endpreis) – rein visuell.
            pass
    else:
        gross = (net * factor_pct).quantize(CENT)
    return {
        "currency": cur,
        "kind": price.kind,
        "interval": price.interval,
        "sub_type": getattr(price, "sub_type", None),
        "net": net,
        "compare_at": compare_at,
        "tax_rate": rate_pct,
        "gross": gross,
    }
