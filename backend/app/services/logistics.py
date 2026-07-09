"""Logistik/Versand (ADR 005): «Versand wird ABGELEITET, nicht bestellt».

Der Bewegungs-Schritt kennt Quelle und Ziel jeder Instanz. Dieses Modul leitet daraus
die **Transportklasse** ab und führt – nur wenn ein externer, physischer Transport
nötig ist – den Versand-Lebenszyklus (Rate-Shopping → Label-Kauf → Tracking):

  1. Ziel **innerhalb** des Betriebs (Geofence/Firmen-Lagerplatz)  → intern, kein Versand.
  2. Ziel = **externe Person** (Kunde/Lieferant)                    → extern (Rollen-Regel,
     funktioniert OHNE Geofence – Mitarbeiter sind innen, Externe aussen).
  3. Ziel-Lagerplatz **ausserhalb** des Geofence-Radius             → extern.
  4. Instanz-Ziele werden über die physische Standort-Kette aufgelöst
     (``locations.resolve_physical_location``) und dann klassifiziert.

**Richtung**: Quelle innen → aussen = ``outbound`` (wir versenden); Quelle aussen →
innen = ``inbound`` (Abholung beim Lieferanten / Kunden-Retoure – Rücktransport über
DIESELBE Engine). Der **Transport-Modus** (auto | carrier | self | none) ist am Schritt
deklariert und je Auftrag am Versand-Beleg übersteuerbar (Long-Tail-Ausnahmen: selbst
bringen/abholen, nie versenden) – maximale Automatik bei voller Abbildbarkeit.

Best-Offer-Policy: **günstigster** Tarif ist die Default-Auswahl; der **schnellste**
wird als Alternative ausgewiesen (``ShipmentRate.cheapest/fastest``).
"""

import math
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Article, ArticleProcessStep, CompanySettings, Instance, Order, Shipment,
    StorageLocation, UserProfile,
)
from ..schemas.shipment import ShipmentEmbed, ShipmentRate
from . import shipping
from .admin import log_audit
from .events import emit
from .locations import resolve_physical_location
from .quantity import to_qty

# Ohne konfigurierten Radius gilt dieser Default (Betriebsgelände eines KMU).
DEFAULT_SITE_RADIUS_M = 300
# Paket-Fallback, wenn der Artikel keine (parsebare) Grösse trägt (cm).
DEFAULT_PARCEL_CM = (30, 20, 15)
DEFAULT_WEIGHT_KG = 0.5

# Rollen, die zum Betrieb gehören (Ziel «Person» ist dann ein interner Handover).
_INTERNAL_ROLES = ("employee", "admin", "ai")

# Länder-Namen → ISO-2 (tolerant; Carrier-APIs verlangen ISO-Codes).
_COUNTRY_ISO2 = {
    "schweiz": "CH", "switzerland": "CH", "suisse": "CH", "ch": "CH",
    "deutschland": "DE", "germany": "DE", "de": "DE",
    "österreich": "AT", "oesterreich": "AT", "austria": "AT", "at": "AT",
    "frankreich": "FR", "france": "FR", "fr": "FR",
    "italien": "IT", "italy": "IT", "it": "IT",
    "liechtenstein": "LI", "li": "LI",
    "usa": "US", "vereinigte staaten": "US", "united states": "US", "us": "US",
    "grossbritannien": "GB", "united kingdom": "GB", "uk": "GB", "gb": "GB",
    "niederlande": "NL", "netherlands": "NL", "nl": "NL",
    "belgien": "BE", "belgium": "BE", "be": "BE",
    "spanien": "ES", "spain": "ES", "es": "ES",
}


def iso2(country: str | None) -> str:
    """Ländername → ISO-2 (tolerant); Default CH (Sitz des Unternehmens)."""
    c = (country or "").strip().lower()
    if not c:
        return "CH"
    if c in _COUNTRY_ISO2:
        return _COUNTRY_ISO2[c]
    return c.upper() if len(c) == 2 else "CH"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreis-Distanz in Metern (für den Geofence-Vergleich)."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _settings(db: Session) -> CompanySettings | None:
    return db.query(CompanySettings).filter(CompanySettings.id == 1).first()


def _inside_geofence(settings: CompanySettings | None, lat, lng) -> bool | None:
    """GPS-Punkt gegen den Betriebs-Geofence prüfen; None = Geofence nicht konfiguriert."""
    if not settings or settings.site_latitude is None or settings.site_longitude is None:
        return None
    if lat is None or lng is None:
        return None
    radius = settings.site_radius_m or DEFAULT_SITE_RADIUS_M
    dist = haversine_m(float(settings.site_latitude), float(settings.site_longitude),
                       float(lat), float(lng))
    return dist <= radius


def classify_target(db: Session, settings: CompanySettings | None,
                    ltype: str | None, lid: int | None) -> str:
    """Ein Standort-Ziel klassifizieren: 'inside' | 'outside' | 'unknown'.

    Personen nach **Rolle** (funktioniert ohne Geofence), Lagerplätze nach **GPS**
    (ohne Geofence/GPS gilt der Firmen-Lagerplatz als innen), Instanzen über die
    physische Standort-Kette."""
    if not ltype or lid is None:
        return "unknown"
    if ltype == "instance":
        pt, pid = resolve_physical_location(db, ltype, lid)
        if (pt, pid) == (ltype, lid):        # Kette endet in sich selbst → unbekannt
            return "unknown"
        return classify_target(db, settings, pt, pid)
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        if not u:
            return "unknown"
        return "inside" if (u.role or "") in _INTERNAL_ROLES else "outside"
    if ltype == "lagerplatz":
        loc = db.query(StorageLocation).filter(StorageLocation.object_id == lid).first()
        if not loc:
            return "unknown"
        fenced = _inside_geofence(settings, loc.latitude, loc.longitude)
        if fenced is None:
            return "inside"    # Konvention: Firmen-Lagerplatz ohne Geofence/GPS = auf dem Gelände
        return "inside" if fenced else "outside"
    if ltype == "company":
        return "inside"
    return "unknown"


def effective_target(db: Session, order: Order, step: ArticleProcessStep) -> tuple[str | None, int | None]:
    """Das für die Klassifikation massgebliche Ziel des Bewegungs-Schritts.

    Pflicht-Versand zum Kunden (mode='customer') → der Kunde des Verkaufs; sonst das
    (optionale) Vorgabe-Ziel der Schritt-Definition. Frei wählbare Ziele (beides leer)
    sind vorab nicht klassifizierbar → (None, None)."""
    if step.mode == "customer":
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        if cust:
            return "user", cust.object_id
        return None, None
    return step.target_location_type, step.target_location_id


def classify_movement(db: Session, order: Order, step: ArticleProcessStep,
                      instances: list[Instance]) -> dict:
    """Transportklasse + Richtung eines Bewegungs-Schritts ableiten.

    Rückgabe: {"transport_class": inside|outside|unknown, "direction": outbound|inbound,
    "target": (typ, id)}. Richtung: Ziel aussen → outbound; Ziel innen, aber Quelle
    (physischer Ist-Standort der Instanzen) aussen → inbound (Abholung/Retoure)."""
    settings = _settings(db)
    t_type, t_id = effective_target(db, order, step)
    target_class = classify_target(db, settings, t_type, t_id)

    src_outside = False
    for inst in instances[:20]:                      # Schutz: grosse Aufträge kappen
        pt, pid = resolve_physical_location(db, inst.location_type, inst.location_id)
        if classify_target(db, settings, pt, pid) == "outside":
            src_outside = True
            break

    if target_class == "outside":
        return {"transport_class": "outside", "direction": "outbound", "target": (t_type, t_id)}
    if target_class == "inside" and src_outside:
        return {"transport_class": "outside", "direction": "inbound", "target": (t_type, t_id)}
    return {"transport_class": target_class, "direction": "outbound", "target": (t_type, t_id)}


# ─── Pakete aus den Artikel-Daten (kaum manueller Input) ─────────────────────────

def parse_dimensions_cm(size: str | None) -> tuple[float, float, float] | None:
    """Grösse-String («3x40x600», mm) → (L, B, H) in cm; None wenn nicht parsebar."""
    if not size:
        return None
    nums = [float(x) for x in re.findall(r"\d+(?:[.,]\d+)?", size.replace(",", "."))][:3]
    if len(nums) < 3:
        return None
    l, w, h = sorted((n / 10.0 for n in nums), reverse=True)   # mm → cm
    return (max(l, 1.0), max(w, 1.0), max(h, 1.0))


def build_parcels(db: Session, instances: list[Instance]) -> tuple[list[dict], bool]:
    """EIN Paket aus den bewegten Instanzen schätzen: Gewicht = Σ (Artikelgewicht × Menge),
    Abmessung = grösste parsebare Artikel-Grösse (sonst Standardkarton). Liefert
    (parcels, hazmat) – hazmat, sobald EIN Artikel als Gefahrgut markiert ist."""
    art_ids = {i.article_id for i in instances if i.article_id}
    articles = {
        a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()
    } if art_ids else {}
    total_kg = Decimal("0")
    dims: tuple[float, float, float] | None = None
    hazmat = False
    for inst in instances:
        art = articles.get(inst.article_id)
        if not art:
            continue
        if art.is_hazmat:
            hazmat = True
        qty = to_qty(inst.quantity or 1)
        if art.weight_kg is not None:
            total_kg += Decimal(str(art.weight_kg)) * qty
        d = parse_dimensions_cm(art.size)
        if d and (dims is None or d[0] * d[1] * d[2] > dims[0] * dims[1] * dims[2]):
            dims = d
    l, w, h = dims or DEFAULT_PARCEL_CM
    weight = float(total_kg) if total_kg > 0 else DEFAULT_WEIGHT_KG
    parcel = {"weight_kg": round(weight, 3), "length_cm": round(l, 1),
              "width_cm": round(w, 1), "height_cm": round(h, 1)}
    return [parcel], hazmat


# ─── Adress-Snapshots ─────────────────────────────────────────────────────────────

def _addr_company(settings: CompanySettings | None) -> dict:
    s = settings
    return {
        "name": (s.company_name if s else None) or "Inexxio",
        "street1": " ".join(x for x in [s.street if s else None, s.street_nr if s else None] if x) or "—",
        "zip": (s.zip_code if s else None) or "",
        "city": (s.city if s else None) or "",
        "country": iso2(s.country if s else None),
        "email": (s.email if s else None) or None,
        "phone": (s.phone if s else None) or None,
    }


def _addr_user(u: UserProfile) -> dict:
    """Empfänger-Adresse einer Person: Lieferadresse (ship_*) vor Wohnadresse."""
    street = u.ship_address_line1 or u.address_line1 or "—"
    return {
        "name": (u.company_name or "").strip() or f"{u.first_name or ''} {u.last_name or ''}".strip() or (u.email or "Empfänger"),
        "street1": street,
        "zip": u.ship_postal_code or u.postal_code or "",
        "city": u.ship_city or u.city or "",
        "country": iso2(u.ship_country or u.country),
        "email": u.email or None,
        "phone": u.phone or None,
    }


def _addr_storage(loc: StorageLocation) -> dict:
    return {
        "name": loc.name or "Lagerplatz",
        "street1": loc.address_street or "—",
        "zip": loc.address_zip or "",
        "city": loc.address_city or "",
        "country": iso2(loc.address_country),
        "email": None, "phone": None,
    }


def _addr_label(a: dict | None) -> str | None:
    if not a:
        return None
    bits = [a.get("name"), a.get("street1"), " ".join(x for x in [a.get("zip"), a.get("city")] if x),
            a.get("country")]
    return " · ".join(str(b) for b in bits if b and b != "—") or None


def target_address(db: Session, ltype: str | None, lid: int | None) -> dict | None:
    """Adress-Snapshot des Ziels (Person → Profil-Adresse, Lagerplatz → Standort-Adresse)."""
    if not ltype or lid is None:
        return None
    if ltype == "instance":
        pt, pid = resolve_physical_location(db, ltype, lid)
        if (pt, pid) == (ltype, lid):
            return None
        return target_address(db, pt, pid)
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        return _addr_user(u) if u else None
    if ltype == "lagerplatz":
        loc = db.query(StorageLocation).filter(StorageLocation.object_id == lid).first()
        return _addr_storage(loc) if loc else None
    return None


# ─── Lebenszyklus (Fachzeile je Bewegungs-Schritt, idempotent) ────────────────────

def _get_shipment(db: Session, order: Order, step: ArticleProcessStep) -> Shipment | None:
    return (
        db.query(Shipment)
        .filter(Shipment.order_id == order.id, Shipment.step_id == step.id,
                Shipment.is_active == True)
        .first()
    )


def ensure_shipment(db: Session, order: Order, step: ArticleProcessStep,
                    instances: list[Instance], actor_id: int) -> Shipment:
    """Versand-Beleg des Schritts holen/anlegen (idempotent) und die abgeleiteten
    Grunddaten (Richtung, Adressen, Pakete, Gefahrgut) auffrischen, solange noch kein
    Label gekauft ist. Committet NICHT."""
    cls = classify_movement(db, order, step, instances)
    ship = _get_shipment(db, order, step)
    if not ship:
        ship = Shipment(order_id=order.id, step_id=step.id, created_by=actor_id,
                        provider=shipping.provider_name())
        db.add(ship)
    if ship.status in ("draft", "quoted"):
        settings = _settings(db)
        t_type, t_id = cls["target"]
        ship.direction = cls["direction"]
        outbound = cls["direction"] == "outbound"
        company = _addr_company(settings)
        other = target_address(db, t_type, t_id)
        ship.address_from = company if outbound else other
        ship.address_to = other if outbound else company
        parcels, hazmat = build_parcels(db, instances)
        ship.parcels = parcels
        ship.hazmat = hazmat
        ship.provider = shipping.provider_name()
    db.flush()
    return ship


def quote(db: Session, order: Order, step: ArticleProcessStep,
          instances: list[Instance], actor_id: int) -> Shipment:
    """Rate-Shopping: Angebote laden und als Snapshot speichern (Status ``quoted``)."""
    ship = ensure_shipment(db, order, step, instances, actor_id)
    if ship.status not in ("draft", "quoted"):
        raise HTTPException(409, detail="Für diesen Versand ist bereits ein Label gekauft")
    if not ship.address_to or not ship.address_from:
        raise HTTPException(400, detail="Empfänger-Adresse unvollständig – bitte Adresse am Ziel (Person/Lagerplatz) pflegen")
    provider = shipping.get_provider()
    if not provider.supports_rates:
        raise HTTPException(503, detail="Kein Versand-Anbieter konfiguriert (EASYPOST_API_KEY) – Carrier/Tracking manuell erfassen")
    result = provider.rates(ship.address_from, ship.address_to, ship.parcels or [])
    raw = result.get("rates") or []
    if not raw:
        raise HTTPException(502, detail="Der Versand-Anbieter hat keine Tarife geliefert")
    ship.provider_shipment_id = result.get("provider_shipment_id")
    raw.sort(key=lambda r: r["amount"])
    fastest = min((r for r in raw if r.get("days") is not None),
                  key=lambda r: (r["days"], r["amount"]), default=None)
    for i, r in enumerate(raw):
        r["cheapest"] = i == 0
        r["fastest"] = fastest is not None and r["rate_id"] == fastest["rate_id"]
    ship.rates = raw
    ship.status = "quoted"
    db.flush()
    log_audit(db, "shipments", None, f"{len(raw)} Versand-Tarife geladen", actor_id,
              object_id=order.object_id)
    emit(db, "shipment.quoted", object_type="order", object_id=order.object_id,
         payload={"rates": len(raw), "direction": ship.direction}, actor_id=actor_id)
    db.commit()
    db.refresh(ship)
    return ship


def buy(db: Session, order: Order, step: ArticleProcessStep, rate_id: str,
        actor_id: int) -> Shipment:
    """Gewähltes Angebot kaufen → Label + Tracking (Status ``purchased``). Idempotent:
    ein bereits gekaufter Versand wird nicht doppelt gekauft."""
    ship = _get_shipment(db, order, step)
    if not ship or not ship.rates:
        raise HTTPException(409, detail="Bitte zuerst Tarife laden")
    if ship.status == "purchased":
        return ship
    rate = next((r for r in ship.rates if r.get("rate_id") == rate_id), None)
    if not rate:
        raise HTTPException(400, detail="Unbekannter Tarif – bitte Tarife neu laden")
    provider = shipping.get_provider()
    result = provider.buy(ship.provider_shipment_id, rate.get("provider_rate_id") or rate_id)
    ship.chosen_rate_id = rate_id
    ship.carrier = rate.get("carrier")
    ship.service = rate.get("service")
    ship.cost_amount = Decimal(str(rate.get("amount") or 0))
    ship.cost_currency = rate.get("currency") or "CHF"
    ship.label_url = result.get("label_url")
    ship.tracking_number = result.get("tracking_number")
    ship.tracking_url = result.get("tracking_url")
    ship.provider_shipment_id = result.get("provider_shipment_id") or ship.provider_shipment_id
    ship.status = "purchased"
    db.flush()
    log_audit(db, "shipments", "label", f"{ship.carrier} {ship.tracking_number or ''}".strip(),
              actor_id, object_id=order.object_id)
    emit(db, "shipment.purchased", object_type="order", object_id=order.object_id,
         payload={"carrier": ship.carrier, "amount": float(ship.cost_amount or 0),
                  "currency": ship.cost_currency, "direction": ship.direction},
         actor_id=actor_id)
    db.commit()
    db.refresh(ship)
    return ship


def apply_update(db: Session, order: Order, step: ArticleProcessStep,
                 instances: list[Instance], data, actor_id: int) -> Shipment:
    """Transport-Modus je Auftrag übersteuern bzw. manuelle Versanddaten erfassen.

    Manuelle Erfassung (Carrier + Tracking) markiert den Versand als ``purchased`` –
    derselbe Endzustand wie der Label-Kauf, nur ohne Aggregator."""
    ship = ensure_shipment(db, order, step, instances, actor_id)
    if data.transport_mode is not None:
        old = ship.transport_mode
        ship.transport_mode = data.transport_mode
        log_audit(db, "shipments", "transport_mode", data.transport_mode, actor_id,
                  object_id=order.object_id, old_value=old)
        if data.transport_mode in ("self", "none"):
            # Kein Carrier → offene Angebots-Daten verwerfen (Label bleibt, falls gekauft).
            if ship.status == "quoted":
                ship.rates = None
                ship.status = "draft"
    if data.carrier is not None:
        ship.carrier = data.carrier.strip() or None
    if data.tracking_number is not None:
        ship.tracking_number = data.tracking_number.strip() or None
    if data.cost_amount is not None:
        ship.cost_amount = Decimal(str(data.cost_amount))
    if data.cost_currency is not None:
        ship.cost_currency = data.cost_currency
    if data.note is not None:
        ship.note = data.note.strip() or None
    if ship.status in ("draft", "quoted") and ship.carrier and ship.tracking_number:
        ship.status = "purchased"      # manuell erfasst = versandbereit
    db.flush()
    db.commit()
    db.refresh(ship)
    return ship


def complete_for_movement(db: Session, order: Order, step: ArticleProcessStep) -> Shipment | None:
    """Beim Quittieren der Bewegung den Versand-Beleg abschliessen (purchased → done).
    Liefert den Beleg (für die Tracking-Übernahme in die Bewegung). Committet NICHT."""
    ship = _get_shipment(db, order, step)
    if ship and ship.status in ("purchased", "quoted", "draft"):
        if ship.status == "purchased":
            ship.status = "done"
        db.flush()
    return ship


# ─── Embed (Auftrag-Detail) ───────────────────────────────────────────────────────

def build_embed(db: Session, order: Order, step: ArticleProcessStep,
                instances: list[Instance]) -> ShipmentEmbed | None:
    """Versand-Stand für das Bewegungs-Embed. ``None``, wenn es nichts Versand-
    Relevantes gibt (frei wählbares Ziel ohne Beleg + Modus auto) – kein UI-Rauschen."""
    ship = _get_shipment(db, order, step)
    cls = classify_movement(db, order, step, instances)
    mode = (ship.transport_mode if ship and ship.transport_mode else None) or step.transport_mode or "auto"
    has_target = cls["target"][0] is not None
    if ship is None and mode == "auto" and (not has_target or cls["transport_class"] != "outside"):
        return None      # nichts abzuleiten und nichts erfasst → keine Box
    if ship is None and mode == "none":
        return None

    emb = ShipmentEmbed(
        id=ship.id if ship else 0,
        exists=ship is not None,
        transport_class=cls["transport_class"],
        direction=(ship.direction if ship else cls["direction"]),
        transport_mode=mode,
        status=ship.status if ship else "draft",
        provider=(ship.provider if ship else shipping.provider_name()),
        provider_ready=shipping.get_provider().supports_rates,
        hazmat=bool(ship.hazmat) if ship else False,
        chosen_rate_id=ship.chosen_rate_id if ship else None,
        carrier=ship.carrier if ship else None,
        service=ship.service if ship else None,
        label_url=ship.label_url if ship else None,
        tracking_number=ship.tracking_number if ship else None,
        tracking_url=ship.tracking_url if ship else None,
        cost_amount=ship.cost_amount if ship else None,
        cost_currency=ship.cost_currency if ship else None,
        note=ship.note if ship else None,
    )
    if ship:
        emb.parcels = ship.parcels or []
        emb.rates = [ShipmentRate(**r) for r in (ship.rates or [])]
        emb.from_label = _addr_label(ship.address_from)
        emb.to_label = _addr_label(ship.address_to)
    else:
        # Vorschau ohne Beleg: Adressen/Pakete live ableiten (kein Schreiben im GET).
        settings = _settings(db)
        t_type, t_id = cls["target"]
        company = _addr_company(settings)
        other = target_address(db, t_type, t_id)
        outbound = cls["direction"] == "outbound"
        emb.from_label = _addr_label(company if outbound else other)
        emb.to_label = _addr_label(other if outbound else company)
        parcels, hazmat = build_parcels(db, instances)
        emb.parcels = parcels
        emb.hazmat = hazmat
    return emb
