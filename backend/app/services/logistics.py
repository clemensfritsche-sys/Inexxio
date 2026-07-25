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
    Article, ArticleProcessStep, CompanySettings, Instance, Order, Shipment, UserProfile,
)
from ..schemas.shipment import ShipmentEmbed, ShipmentRate
from . import shipping
from .admin import log_audit
from .events import emit
from .locations import resolve_physical_location, resolve_physical_place
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


def _norm(v) -> str:
    """Adress-Bestandteil normalisieren (Klein, ohne Sonderzeichen) für den Vergleich."""
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def _has_address(a: dict | None) -> bool:
    """Trägt der Adress-Snapshot echte Angaben (PLZ oder Ort)? «—»/leer zählt nicht."""
    if not a:
        return False
    return bool((a.get("zip") or "").strip() or (a.get("city") or "").strip())


def same_place(a: dict | None, b: dict | None) -> bool:
    """Zwei Adress-Snapshots als **gleicher Ort** werten (Strasse+PLZ+Ort+Land normalisiert)."""
    if not _has_address(a) or not _has_address(b):
        return False
    ka = (_norm(a.get("street1")), _norm(a.get("zip")), _norm(a.get("city")), _norm(a.get("country")))
    kb = (_norm(b.get("street1")), _norm(b.get("zip")), _norm(b.get("city")), _norm(b.get("country")))
    return ka == kb


def location_kind(db: Session, ltype: str | None, lid: int | None) -> str:
    """Ownership eines Standort-Ziels: 'external_person' (Kunde/Lieferant) |
    'internal' (Ort/Mitarbeiter/Firma/Behälter) | 'unknown'. Instanzen über die
    physische Standort-Kette.

    Ein **Ort** gilt als *internal* – er ist ein von uns gesetzter Standort. Ob daraus
    ein Versand wird, entscheidet danach der **Adressvergleich** (andere Anschrift als
    die Quelle → Transport); genau so verhält sich schon der Mehr-Standort-Fall."""
    if ltype == "place":
        return "internal"
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


def effective_target(db: Session, order: Order, step: ArticleProcessStep) -> tuple[str | None, int | None, dict | None]:
    """Das für die Klassifikation massgebliche Ziel des Bewegungs-Schritts –
    ``(typ, objektnummer, ort)``; bei einem **Ort** ist die Nummer ``None`` und der
    Adress-Snapshot gesetzt.

    Pflicht-Versand zum Kunden (mode='customer') → der Kunde des Verkaufs; sonst das
    (optionale) Vorgabe-Ziel der Schritt-Definition. Frei wählbare Ziele (alles leer)
    sind vorab nicht klassifizierbar → (None, None, None)."""
    if step.mode == "customer":
        from .sale import customer_for_order
        cust = customer_for_order(db, order)
        if cust:
            return "user", cust.object_id, None
        return None, None, None
    if step.target_location_type == "place":
        return "place", None, step.target_place
    return step.target_location_type, step.target_location_id, None


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
    t_type, t_id, t_place = effective_target(db, order, step)
    tgt_kind = location_kind(db, t_type, t_id)

    # Quelle = physischer Ist-Standort der ersten verorteten Instanz (Ort ODER Objekt).
    s_type = s_id = None
    s_place = None
    for inst in instances[:20]:                      # Schutz: grosse Aufträge kappen
        if inst.location_type == "place" and inst.place:
            s_type, s_id, s_place = "place", None, inst.place
            break
        pt, pid = resolve_physical_location(db, inst.location_type, inst.location_id)
        if pt == "place":
            # Die Kette endet an einem Ort (z. B. Bauteil → Behälter → Adresse).
            s_type, s_id, s_place = "place", None, resolve_physical_place(
                db, inst.location_type, inst.location_id)
            break
        if pt and pid:
            s_type, s_id = pt, pid
            break
    src_kind = location_kind(db, s_type, s_id)

    target = (t_type, t_id, t_place)
    if tgt_kind == "external_person":
        return {"transport_class": "outside", "direction": "outbound", "target": target}
    if src_kind == "external_person":
        return {"transport_class": "outside", "direction": "inbound", "target": target}
    if tgt_kind == "unknown":
        return {"transport_class": "unknown", "direction": "outbound", "target": target}
    # Beide intern → Adress-Vergleich (Mehr-Standort). Ziel ohne Adresse = innerbetrieblich.
    tgt_addr = target_address(db, t_type, t_id, t_place)
    src_addr = target_address(db, s_type, s_id, s_place)
    if _has_address(tgt_addr) and _has_address(src_addr) and not same_place(src_addr, tgt_addr):
        return {"transport_class": "outside", "direction": "outbound", "target": target}
    return {"transport_class": "inside", "direction": "outbound", "target": target}


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


def _addr_place(place: dict) -> dict:
    """Adress-Snapshot eines **Orts** – er liegt bereits in genau dieser Form vor
    (``schemas/place.py``), nur Land normalisieren und Lücken auffüllen."""
    return {
        "name": (place.get("name") or "").strip() or "Standort",
        "street1": (place.get("street1") or "").strip() or "—",
        "zip": (place.get("zip") or "").strip() or "",
        "city": (place.get("city") or "").strip() or "",
        "country": iso2(place.get("country")),
        "email": None, "phone": None,
    }


def _addr_label(a: dict | None) -> str | None:
    if not a:
        return None
    bits = [a.get("name"), a.get("street1"), " ".join(x for x in [a.get("zip"), a.get("city")] if x),
            a.get("country")]
    return " · ".join(str(b) for b in bits if b and b != "—") or None


def target_address(db: Session, ltype: str | None, lid: int | None,
                   place: dict | None = None) -> dict | None:
    """Adress-Snapshot des Ziels: **Ort** → seine eigene Adresse, Person → Profil-Adresse,
    **Unternehmen** → Firmenadresse, Instanz → über die physische Kette (endet an einem
    Ort/einer Person/dem Unternehmen)."""
    if ltype == "place":
        return _addr_place(place) if place else None
    if not ltype or lid is None:
        return None
    if ltype == "instance":
        pt, pid = resolve_physical_location(db, ltype, lid)
        if (pt, pid) == (ltype, lid):
            return None
        if pt == "place":
            # Kette endet an einem Ort – dessen Adresse liegt an der Host-Instanz.
            host_place = resolve_physical_place(db, ltype, lid)
            return _addr_place(host_place) if host_place else None
        return target_address(db, pt, pid)
    if ltype == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == lid).first()
        return _addr_user(u) if u else None
    if ltype == "company":
        # Das Unternehmen selbst – bisher hatte es KEINEN Adress-Zweig, obwohl
        # ``location_kind`` es als intern führte (stille Lücke). Jetzt als Bewegungsziel
        # zugelassen und darum sauber aufgelöst.
        return _addr_company(_settings(db))
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
        t_type, t_id, t_place = cls["target"]
        ship.direction = cls["direction"]
        outbound = cls["direction"] == "outbound"
        company = _addr_company(settings)
        other = target_address(db, t_type, t_id, t_place)
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
        raise HTTPException(400, detail="Empfänger-Adresse unvollständig – bitte Adresse am Ziel (Ort/Person/Unternehmen) pflegen")
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
        emb.from_label = _addr_label(ship.address_from)
        emb.to_label = _addr_label(ship.address_to)
    else:
        # Vorschau ohne Beleg: Adressen/Pakete/Last live ableiten (kein Schreiben im GET).
        settings = _settings(db)
        t_type, t_id, t_place = cls["target"]
        company = _addr_company(settings)
        other = target_address(db, t_type, t_id, t_place)
        outbound = cls["direction"] == "outbound"
        emb.from_label = _addr_label(company if outbound else other)
        emb.to_label = _addr_label(other if outbound else company)
        parcels, hazmat = build_parcels(db, instances)
        emb.parcels = parcels
        emb.hazmat = hazmat
        emb.load = load if kind == "freight" else None
    return emb
