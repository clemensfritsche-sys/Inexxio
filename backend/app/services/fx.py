"""Wechselkurse – **Tageskurs** mit unveränderlicher Historie (``fx_rates``).

Leitlinie (siehe Aufgabe): **innerhalb eines Tages stabil.** ``get_rate`` liefert den
für (Tag, Währung) gespeicherten Kurs; fehlt er, wird er **einmal** von einer kostenlosen
Quelle (Env ``FX_SOURCE_URL``, exchangerate.host-Format) geholt und gespeichert. Schlägt
der Abruf fehl, wird der **letzte bekannte** Kurs verwendet (best-effort). CHF = 1.0.

Bewusst NICHT gebaut (Schlankheit): Mehrtages-Pinning mit Drift-Schwelle – Tageskurs +
Within-Day-Persistenz genügen. Ein PPP-/Zonen-Multiplikator wäre eine **spätere** optionale
Stufe (siehe ``services/pricing.py``).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import FxRate
from ..models.base import utcnow

ONE = Decimal("1")

# In-Prozess-Memo je (Währung, Tag): ein gespeicherter Tageskurs ist unveränderlich
# (``_persist`` überspringt Vorhandenes) – erspart dem Shop-Listing einen Query je
# Preis×Währung. Der Last-known-Fallback wird bewusst NICHT gecacht (er kann sich
# im Tagesverlauf noch durch einen erfolgreichen Abruf verbessern).
_rate_memo: dict[tuple[str, date], Decimal] = {}


def _today() -> date:
    return utcnow().date()


def _stored(db: Session, currency: str, day: date) -> Decimal | None:
    row = (
        db.query(FxRate)
        .filter(FxRate.currency == currency, FxRate.day == day)
        .first()
    )
    return row.rate_to_chf if row else None


def _last_known(db: Session, currency: str) -> Decimal | None:
    row = (
        db.query(FxRate)
        .filter(FxRate.currency == currency)
        .order_by(FxRate.day.desc())
        .first()
    )
    return row.rate_to_chf if row else None


def _fetch_rates_to_chf() -> dict[str, Decimal]:
    """Tageskurse aller Währungen → CHF von der konfigurierten Quelle.

    exchangerate.host (Basis CHF) liefert ``rates[CUR]`` = Wert von 1 CHF in CUR;
    der Kurs **nach CHF** ist der Kehrwert. Best-effort: bei jedem Fehler ``{}``."""
    settings = get_settings()
    url = settings.fx_source_url
    if not url:
        return {}
    try:
        import httpx

        resp = httpx.get(url, params={"base": "CHF"}, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates") or {}
        out: dict[str, Decimal] = {}
        for cur, val in rates.items():
            try:
                v = Decimal(str(val))
            except Exception:
                continue
            if v > 0:
                out[cur.upper()] = (ONE / v).quantize(Decimal("0.00000001"))
        out["CHF"] = ONE
        return out
    except Exception as e:  # noqa: BLE001 – FX-Abruf darf nie etwas brechen
        print(f"WARNING: FX fetch failed: {e}", flush=True)
        return {}


def _persist(db: Session, day: date, rates: dict[str, Decimal]) -> None:
    """Geholte Tageskurse einfügen (idempotent: vorhandene (Tag, Währung) überspringen)."""
    for cur, rate in rates.items():
        if _stored(db, cur, day) is not None:
            continue
        db.add(FxRate(day=day, currency=cur, rate_to_chf=rate, source="exchangerate.host"))
    db.commit()


def get_rate(db: Session, currency: str, day: date | None = None) -> Decimal:
    """Wechselkurs einer Währung → CHF für ``day`` (Default heute). CHF = 1.0.

    Reihenfolge: gespeicherter Tageskurs → einmaliger Abruf + Speichern → letzter
    bekannter Kurs → 1.0 (Notfall). Innerhalb eines Tages konstant."""
    cur = (currency or "CHF").upper()
    if cur == "CHF":
        return ONE
    day = day or _today()
    memo = _rate_memo.get((cur, day))
    if memo is not None:
        return memo
    existing = _stored(db, cur, day)
    if existing is not None:
        _rate_memo[(cur, day)] = existing
        return existing
    fetched = _fetch_rates_to_chf()
    if fetched:
        _persist(db, day, fetched)
        if cur in fetched:
            _rate_memo[(cur, day)] = fetched[cur]
            return fetched[cur]
    last = _last_known(db, cur)
    return last if last is not None else ONE
