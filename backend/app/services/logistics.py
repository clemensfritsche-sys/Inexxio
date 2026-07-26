"""Logistik/Versand (ADR 005): «Versand wird ABGELEITET, nicht bestellt».

Der Bewegungs-Schritt kennt Quelle und Ziel jeder Instanz. Dieses Modul leitet daraus
die **Transportklasse** ab – **adress-basiert, KEIN Geofence** (bewusst einfach & universell)
– und führt, nur wenn ein externer, physischer Transport nötig ist, den Versand-Lebenszyklus
(Rate-Shopping → Label-Kauf → Tracking):

  1. Ziel = **externe Person** (Kunde/Lieferant, per Rolle)         → extern, outbound.
  2. Quelle = externe Person (Ware liegt beim Kunden/Lieferanten)  → extern, inbound
     (Abholung beim Lieferanten / Kunden-Retoure – Rücktransport über DIESELBE Engine).
  3. Ziel **ohne bekannten Standort/Adresse**                       → innerbetrieblich (kein Versand).
  4. Zwei **interne** Orte: Versand NUR, wenn beide eine **Adresse** tragen und sich
     **unterscheiden** (Mehr-Standort-Transport A→B). Gleiche/keine Adresse → innerbetrieblich.

So braucht es keinen Geofence: «von A nach B mit anderer Adresse → Versand, sonst intern».
Instanz-Ziele werden über die physische Standort-Kette aufgelöst (``resolve_physical_location``).
Aus Klasse **und** geschätzter Last leitet ``recommend_mode`` **einen** Transport-Modus als
Empfehlung ab – **internal** (innerbetrieblich, kein Carrier) | **parcel** (Paket) |
**freight** (Stückgut/Palette). Diese Empfehlung ist die vorgewählte Default-Auswahl und je
Auftrag am Versand-Beleg frei übersteuerbar (``shipments.transport_mode``) – der Nutzer wählt
IMMER zwischen den drei Optionen, die Ableitung nimmt ihm nur die Vorauswahl ab.

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
    UserProfile,
)
from ..schemas.shipment import ShipmentEmbed, ShipmentRate
from . import address, shipping
from .admin import log_audit
from .events import emit
from .locations import resolve_physical_location
from .quantity import to_qty

# Paket-Fallback, wenn der Artikel keine (parsebare) Grösse trägt (cm).
DEFAULT_PARCEL_CM = (30, 20, 15)
DEFAULT_WEIGHT_KG = 0.5

# Phase-0-Fracht: Schwelle Paket ↔ Stückgut. Darüber ist Paket-Rate-Shopping unrealistisch
# → Fracht (Palette/Lademeter, manuell/Spediteur). Grobe, bewusst einfache Kennzahlen.
PARCEL_MAX_KG = 31.5          # gängige Paket-Obergrenze der Carrier
PARCEL_MAX_VOLUME_M3 = 0.20   # ~ grösserer Karton; darüber palettiert
PALLET_MAX_KG = 700.0         # Tragfähigkeit je EUR-Palette (Schätzung)
PALLET_VOLUME_M3 = 0.8        # nutzbares Volumen je EUR-Palette (~120×80×85 cm)
PALLET_LOADING_METERS = 0.4   # Lademeter je EUR-Palette (2 nebeneinander = 1 LM)

# Rollen, die zum Betrieb gehören (Ziel «Person» ist dann ein interner Handover).
_INTERNAL_ROLES = ("employee", "admin", "ai")

# Länder-Normalisierung lebt in ``services/address.py`` (eine Wahrheit für alle
# Adress-Verwender); hier als Alias, damit bestehende Aufrufer unverändert bleiben.
iso2 = address.iso2


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


def location_kind(db: Session, ltype: str | None, lid: int | None) -> str:
    """Ownership eines Standort-Ziels: 'external_person' (Kunde/Lieferant) |
    'internal' (Mitarbeiter/Firma) | 'unknown'. Instanzen über die physische
    Standort-Kette."""
    if not ltype or lid is None:
        return "unknown"
    if ltype == "instance":
        pt, pid = resolve_physical_location(db, ltype, lid)
        if (pt, pid) == (ltype, lid):        # Kette endet in sich selbst → unbekannt
            return "unknown"
        return location_kind(db, pt, pid)
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        if not u:
            return "unknown"
        return "internal" if (u.role or "") in _INTERNAL_ROLES else "external_person"
    if ltype == "company":
        return "internal"
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
    """Transportklasse + Richtung eines Bewegungs-Schritts ableiten – **adress-basiert,
    ohne Geofence**. Rückgabe: {"transport_class": inside|outside|unknown,
    "direction": outbound|inbound, "target": (typ, id)}.

    Regeln (einfach & universell):
      • Ziel = **externe Person** (Kunde/Lieferant)            → extern, outbound.
      • Quelle = externe Person (Ware liegt beim Kunden/Lief.) → extern, inbound (Abholung/Retoure).
      • Ziel ohne bekannten Standort/Adresse                   → intern (kein Versand).
      • Zwei interne Orte: Versand NUR, wenn **beide eine Adresse tragen und sich
        UNTERSCHEIDEN** (Mehr-Standort-Transport). Gleiche/keine Adresse → **innerbetrieblich**.
    """
    t_type, t_id = effective_target(db, order, step)
    tgt_kind = location_kind(db, t_type, t_id)

    # Quelle = physischer Ist-Standort der ersten verorteten Instanz.
    s_type = s_id = None
    for inst in instances[:20]:                      # Schutz: grosse Aufträge kappen
        pt, pid = resolve_physical_location(db, inst.location_type, inst.location_id)
        if pt and pid:
            s_type, s_id = pt, pid
            break
    src_kind = location_kind(db, s_type, s_id)

    if tgt_kind == "external_person":
        return {"transport_class": "outside", "direction": "outbound", "target": (t_type, t_id)}
    if src_kind == "external_person":
        return {"transport_class": "outside", "direction": "inbound", "target": (t_type, t_id)}
    if tgt_kind == "unknown":
        return {"transport_class": "unknown", "direction": "outbound", "target": (t_type, t_id)}
    # Beide intern → Adress-Vergleich (Mehr-Standort). Ziel ohne Adresse = innerbetrieblich.
    tgt_addr = target_address(db, t_type, t_id)
    src_addr = target_address(db, s_type, s_id)
    if address.has_content(tgt_addr) and address.has_content(src_addr) and not address.same(src_addr, tgt_addr):
        return {"transport_class": "outside", "direction": "outbound", "target": (t_type, t_id)}
    return {"transport_class": "inside", "direction": "outbound", "target": (t_type, t_id)}


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


def _instance_volume_m3(art) -> float:
    """Einzel-Volumen (m³) aus der Artikel-Grösse; 0, wenn nicht parsebar."""
    d = parse_dimensions_cm(getattr(art, "size", None))
    return (d[0] * d[1] * d[2]) / 1_000_000.0 if d else 0.0


def build_load(db: Session, instances: list[Instance]) -> dict:
    """Fracht-Last aus den bewegten Instanzen schätzen (Phase 0): Gesamt-Bruttogewicht,
    Volumen, Paletten (Max aus Gewichts-/Volumenbedarf) und Lademeter. Bewusst grob –
    der Spediteur bzw. die manuelle Erfassung präzisiert."""
    art_ids = {i.article_id for i in instances if i.article_id}
    articles = {
        a.id: a for a in db.query(Article).filter(Article.id.in_(art_ids)).all()
    } if art_ids else {}
    total_kg = Decimal("0")
    total_vol = 0.0
    for inst in instances:
        art = articles.get(inst.article_id)
        if not art:
            continue
        qty = to_qty(inst.quantity or 1)
        if art.weight_kg is not None:
            total_kg += Decimal(str(art.weight_kg)) * qty
        total_vol += _instance_volume_m3(art) * float(qty)
    gross = float(total_kg)
    if gross > 0 or total_vol > 0:
        pallets = max(1, math.ceil(max(gross / PALLET_MAX_KG, total_vol / PALLET_VOLUME_M3)))
    else:
        pallets = 1
    return {
        "pallets": pallets,
        "pallet_type": "EUR",
        "loading_meters": round(pallets * PALLET_LOADING_METERS, 2),
        "volume_m3": round(total_vol, 3),
        "gross_weight_kg": round(gross, 3),
        "stackable": True,
    }


def derive_kind(gross_weight_kg: float, volume_m3: float) -> str:
    """Sendungsart aus der Last ableiten: über der Paket-Obergrenze (Gewicht ODER Volumen)
    → 'freight' (Stückgut/Palette), sonst 'parcel'."""
    if gross_weight_kg > PARCEL_MAX_KG or volume_m3 > PARCEL_MAX_VOLUME_M3:
        return "freight"
    return "parcel"


def recommend_mode(cls: dict, load: dict) -> str:
    """Empfohlener Transport-Modus (Default-Auswahl, IMMER übersteuerbar): verlangt die
    Klassifikation keinen externen Transport → **internal** (innerbetrieblich); sonst je
    geschätzter Last **parcel** (Paket) oder **freight** (Stückgut/Palette)."""
    if cls.get("transport_class") != "outside":
        return "internal"
    return derive_kind(load.get("gross_weight_kg", 0.0), load.get("volume_m3", 0.0))


# ─── Adress-Snapshots ─────────────────────────────────────────────────────────────

# Adress-Aufbau ist zentral in ``services/address.py`` – hier wird direkt dorthin
# gerufen. Die früheren Ein-Zeilen-Aliase (_addr_company/_addr_user/_addr_label/
# _has_address/same_place) waren reine Weiterleitung und sind entfallen: eine
# Indirektion, die nichts hinzufügte, aber eine zweite Namensebene für dieselbe Sache
# schuf.
def _addr_company(settings: CompanySettings | None) -> dict:
    """Firmenadresse mit Rückfall auf den blossen Namen (Snapshot braucht ein Ziel)."""
    return address.of_company(settings) if settings else address.make(name="Inexxio")


def target_address(db: Session, ltype: str | None, lid: int | None) -> dict | None:
    """Adress-Snapshot des Ziels (Person → Profil-Adresse, Unternehmen → Firmensitz)."""
    if not ltype or lid is None:
        return None
    if ltype == "instance":
        pt, pid = resolve_physical_location(db, ltype, lid)
        if (pt, pid) == (ltype, lid):
            return None
        return target_address(db, pt, pid)
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        return address.of_user(u, "ship") if u else None
    if ltype == "company":
        # «Im Betrieb» – die Firmenadresse. Ohne diesen Zweig hätte eine Bewegung mit
        # Ziel Unternehmen keinen Empfänger und liefe in «Adresse unvollständig».
        return _addr_company(db.query(CompanySettings).first())
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
    parcels, hazmat = build_parcels(db, instances)
    load = build_load(db, instances)
    if not ship:
        # ``status`` + ``kind`` EXPLIZIT setzen: die Spalten-Defaults greifen erst beim Flush,
        # der Block unten läuft aber DAVOR – ohne dies bliebe ``status`` None (Adressen würden
        # übersprungen) bzw. ``kind`` None. Die Sendungsart wird bei der Anlage aus der Last
        # abgeleitet (Gewicht/Volumen → parcel|freight), danach am Beleg übersteuerbar.
        ship = Shipment(order_id=order.id, step_id=step.id, created_by=actor_id,
                        status="draft", provider=shipping.provider_name(),
                        kind=derive_kind(load["gross_weight_kg"], load["volume_m3"]))
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
        ship.parcels = parcels
        ship.hazmat = hazmat
        # Last nur bei Fracht führen (die geschätzte grundieren; manuelle Verfeinerung
        # bleibt via apply_update erhalten). ``kind`` selbst bleibt (Override sticky).
        ship.load = {**load, **(ship.load or {})} if ship.kind == "freight" else None
        ship.provider = shipping.provider_name()
    db.flush()
    return ship


def quote(db: Session, order: Order, step: ArticleProcessStep,
          instances: list[Instance], actor_id: int) -> Shipment:
    """Rate-Shopping: Angebote laden und als Snapshot speichern (Status ``quoted``)."""
    ship = ensure_shipment(db, order, step, instances, actor_id)
    if ship.status not in ("draft", "quoted"):
        raise HTTPException(409, detail="Für diesen Versand ist bereits ein Label gekauft")
    if ship.kind == "freight":
        raise HTTPException(400, detail="Fracht (Stückgut/Palette) läuft nicht über das Paket-"
                            "Rate-Shopping – Spediteur anfragen und Carrier/Tracking/Kosten "
                            "manuell erfassen (Instant-Fracht-Tarif folgt als Phase 1).")
    if not ship.address_to or not ship.address_from:
        raise HTTPException(400, detail="Empfänger-Adresse unvollständig – bitte Adresse am Ziel (Person/Unternehmen) pflegen")
    provider = shipping.get_provider()
    if not provider.supports_rates:
        raise HTTPException(503, detail="Kein Versand-Anbieter konfiguriert (SHIPPO_API_KEY) – Carrier/Tracking manuell erfassen")
    result = provider.rates(ship.address_from, ship.address_to, ship.parcels or [])
    raw = result.get("rates") or []
    if not raw:
        # Leere Tarifliste ist KEIN Absturz – der Anbieter erklärt den Grund in ``messages``.
        # Sind alle Meldungen «Herkunft/Service-Area nicht unterstützt» (der Normalfall in der
        # Shippo-Testumgebung: die geteilten Test-Carrier versenden nur ab US/DE/FR/UK/ES, es gibt
        # kein CH-Test-Konto), fassen wir das lesbar zusammen statt 15 Carrier-Zeilen zu zeigen.
        msgs = result.get("messages") or []
        origin = (ship.address_from or {}).get("country") or "?"
        joined = " ".join(msgs).lower()
        coverage = bool(msgs) and any(
            k in joined for k in ("support", "service area", "origin", "restricted", "outside of"))
        if coverage:
            detail = (f"Keine Versand-Tarife: kein verbundenes Carrier-Konto bedient die Herkunft «{origin}». "
                      "In der Shippo-Testumgebung versenden die geteilten Test-Carrier nur ab US/DE/FR/UK/ES "
                      "– es gibt kein Schweizer Test-Konto. Für den Echtbetrieb ein eigenes CH-Carrier-Konto "
                      "(z. B. Swiss Post/DHL) in Shippo verbinden; zum Ausprobieren eine unterstützte "
                      "Herkunft verwenden.")
        elif msgs:
            detail = "Keine Versand-Tarife geliefert. Anbieter-Hinweis: " + " · ".join(msgs)
        else:
            detail = (f"Keine Versand-Tarife geliefert – vermutlich ist kein Carrier-Konto mit Herkunft "
                      f"«{origin}» verbunden (in Shippo unter «Carriers» aktivieren).")
        raise HTTPException(502, detail=detail)
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
    result = provider.buy(
        {"provider_shipment_id": ship.provider_shipment_id, "address_from": ship.address_from,
         "address_to": ship.address_to, "parcels": ship.parcels or []},
        rate.get("provider_rate_id") or rate_id)
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
    # Transport-Modus setzen – EINE Achse (internal | parcel | freight). Der Modus ist
    # autoritativ und leitet die interne Sendungsart (``kind``) ab: 'freight' führt eine
    # Fracht-Last, 'parcel' die Paketmasse, 'internal' keinen Carrier (kein Versand).
    if data.transport_mode is not None and data.transport_mode != ship.transport_mode:
        old = ship.transport_mode
        ship.transport_mode = data.transport_mode
        ship.kind = "freight" if data.transport_mode == "freight" else "parcel"
        ship.load = build_load(db, instances) if ship.kind == "freight" else None
        log_audit(db, "shipments", "transport_mode", data.transport_mode, actor_id,
                  object_id=order.object_id, old_value=old)
        if data.transport_mode == "internal" and ship.status == "quoted":
            # Innerbetrieblich → kein Carrier: offene Angebots-Daten verwerfen (ein bereits
            # gekauftes Label bliebe erhalten).
            ship.rates = None
            ship.status = "draft"
    # Fracht-Last manuell verfeinern (Merge über die geschätzte).
    if data.load is not None:
        ship.load = {**(ship.load or {}), **data.load}
    if data.incoterm is not None:
        ship.incoterm = data.incoterm or None
    if data.pickup_date is not None:
        ship.pickup_date = data.pickup_date or None
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
    """Versand-Stand für das Bewegungs-Embed. Für einen Bewegungs-Schritt IMMER vorhanden –
    der Nutzer wählt stets zwischen **innerbetrieblich / Paket / Fracht**; der abgeleitete
    Modus (``recommended_mode``) ist nur die vorgewählte Empfehlung. Ein am Beleg gesetzter
    Modus (``ship.transport_mode``) übersteuert die Empfehlung."""
    ship = _get_shipment(db, order, step)
    cls = classify_movement(db, order, step, instances)
    load = build_load(db, instances)
    recommended = recommend_mode(cls, load)
    mode = (ship.transport_mode if ship and ship.transport_mode else None) or recommended
    kind = "freight" if mode == "freight" else "parcel"

    emb = ShipmentEmbed(
        id=ship.id if ship else 0,
        exists=ship is not None,
        transport_class=cls["transport_class"],
        direction=(ship.direction if ship else cls["direction"]),
        transport_mode=mode,
        recommended_mode=recommended,
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
        kind=kind,
        incoterm=(ship.incoterm if ship else None),
        pickup_date=(ship.pickup_date if ship else None),
    )
    if ship:
        emb.parcels = ship.parcels or []
        emb.load = ship.load if kind == "freight" else None
        emb.rates = [ShipmentRate(**r) for r in (ship.rates or [])]
        emb.from_label = address.one_line(ship.address_from)
        emb.to_label = address.one_line(ship.address_to)
    else:
        # Vorschau ohne Beleg: Adressen/Pakete/Last live ableiten (kein Schreiben im GET).
        settings = _settings(db)
        t_type, t_id = cls["target"]
        company = _addr_company(settings)
        other = target_address(db, t_type, t_id)
        outbound = cls["direction"] == "outbound"
        emb.from_label = address.one_line(company if outbound else other)
        emb.to_label = address.one_line(other if outbound else company)
        parcels, hazmat = build_parcels(db, instances)
        emb.parcels = parcels
        emb.hazmat = hazmat
        emb.load = load if kind == "freight" else None
    return emb
