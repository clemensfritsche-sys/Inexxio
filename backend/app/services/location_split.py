"""Standort-Verteilung einer Charge – **mengengenau, ohne Teilung der Instanz**.

Exakt nach dem Vorbild von ``services/reservation.py``: die universelle Objektnummer
einer Instanz ist physisch (Etikett/QR an den Teilen) und darf sich **nie** ändern; eine
Charge wird **nie** in eine zweite Instanz mit eigener Nummer aufgeteilt. Statt zu teilen,
merkt sich die **eine** Instanz eine **Standort→Menge-Map** (``instances.locations``):

    locations = {"100000123": {"t": "instance", "q": "300"},   # Behälter «Band A»
                 "100000124": {"t": "instance", "q": "700"}}    # Behälter «Band B»  (Σ = quantity)

Geschlüsselt nach **Objektnummer** des Ziels (global eindeutig → «wer liegt hier?» per
``locations ? '<objektnr>'``). **Verteilbar sind darum nur Halter MIT Objektnummer**
(Instanz/Person/Unternehmen); ein ``place`` (reine Adresse) hält per Definition die ganze
(Rest-)Menge. Das ist keine Einschränkung, sondern die ehrliche Abbildung: eine Adresse
kann zwei Plätze am selben Standort gar nicht unterscheiden – wer innerhalb eines
Standorts verteilen will, nutzt **Behälter-Instanzen** (die tragen eine Nummer und ein
Etikett). Ist die Charge an EINEM Ort (Normalfall) → Map ``None``,
der Skalar ``location_type/location_id`` ist die Wahrheit. Verteilt → die Map ist die
Wahrheit, der Skalar spiegelt die **grösste** Teilmenge (denormalisiert, wie
``reserved_for_order_id`` die Einzel-Reservierung spiegelt).

**Bruchmengen:** alle Mengen sind ``Decimal`` (kg/m²/…), JSON-sicher als String abgelegt
und ausschliesslich über ``services/quantity.py`` gerechnet. Dies ist die EINE Schreibstelle
für die Verteilung.
"""

import re
from decimal import Decimal

from fastapi import HTTPException

from ..models import Instance
from .quantity import ZERO, qty_key, to_qty

# Ein Slice: Ziel-Objektnummer → (Standort-Typ, Menge).
Slice = tuple[str, Decimal]


def _load_map(inst: Instance) -> dict[int, Slice]:
    """Nur die persistierte Map einlesen (``{objektnr: (typ, Decimal)}``) – leer, wenn keine."""
    out: dict[int, Slice] = {}
    for k, v in (inst.locations or {}).items():
        try:
            out[int(k)] = (str(v.get("t")), to_qty(v.get("q")))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def _seed_from_scalar(inst: Instance) -> dict[int, Slice]:
    """Arbeitsverteilung: die Map, sonst die ganze Menge am skalaren Standort.

    Ein **Ort** (``location_type='place'``) hat keine Objektnummer und kann daher nicht
    Schlüssel der Verteilung sein – er hält per Definition die ganze (Rest-)Menge und
    ergibt hier eine leere Verteilung."""
    m = _load_map(inst)
    if m:
        return _trim(m, to_qty(inst.quantity))
    if inst.location_id is not None and inst.location_type and inst.location_type != "place":
        return {int(inst.location_id): (inst.location_type, to_qty(inst.quantity))}
    return {}


def _trim(m: dict[int, Slice], cap: Decimal) -> dict[int, Slice]:
    """Verteilung auf ``cap`` (= quantity) deckeln: übersteigt die Summe die Menge
    (z. B. nach Teil-Verschrottung), grösste Slices zuerst herunterkürzen. Rein."""
    m = {k: v for k, v in m.items() if v[1] > 0}
    total = sum((v[1] for v in m.values()), ZERO)
    while m and total > cap:
        k = max(m, key=lambda x: m[x][1])
        over = total - cap
        t, q = m[k]
        new_q = q - over
        if new_q > 0:
            m[k] = (t, new_q)
            total = cap
        else:
            del m[k]
            total -= q
    return m


def _write(inst: Instance, m: dict[int, Slice]) -> None:
    """Verteilung + Denormalisierungen konsistent zurückschreiben (die EINE Stelle):
    nicht-positive Slices verwerfen; bei ≤1 Slice ist die Map ``None`` und der Skalar
    die Wahrheit; bei ≥2 Slices trägt die Map die Wahrheit und der Skalar die grösste
    Teilmenge (denormalisiert)."""
    clean = {k: v for k, v in m.items() if v[1] > 0}
    if not clean:
        inst.locations = None
        return
    # Skalar = grösste Teilmenge (bei Gleichstand die kleinste Objektnummer → stabil).
    primary = max(clean, key=lambda k: (clean[k][1], -k))
    inst.location_type, inst.location_id = clean[primary][0], primary
    if len(clean) == 1:
        inst.locations = None
    else:
        inst.locations = {str(k): {"t": t, "q": qty_key(q)} for k, (t, q) in clean.items()}


def distribution(inst: Instance) -> list[dict]:
    """Effektive Standort-Verteilung (auf ``quantity`` abgeglichen) als Liste –
    ``[{location_type, location_id, quantity}]``. Bei EINEM Standort ein Eintrag; ohne
    Standort leer. Reine Ableitung (schreibt nicht)."""
    if inst.location_type == "place":
        # Ein Ort hält immer die ganze Menge (keine Objektnummer → nicht verteilbar).
        return [{"location_type": "place", "location_id": None, "quantity": float(to_qty(inst.quantity))}]
    m = _seed_from_scalar(inst)
    return [
        {"location_type": t, "location_id": oid, "quantity": float(q)}
        for oid, (t, q) in sorted(m.items(), key=lambda kv: kv[1][1], reverse=True)
        if q > 0
    ]


def reconcile(inst: Instance) -> None:
    """Persistente Map auf die aktuelle ``quantity`` abgleichen (nach Mengen-Abgang,
    z. B. Teil-Verschrottung/Verbrauch). No-op, wenn keine Map."""
    if inst.locations:
        _write(inst, _trim(_load_map(inst), to_qty(inst.quantity)))


def set_single(inst: Instance, location_type: str, location_id: int) -> None:
    """Ganze Instanz an EINEN objektbasierten Standort – Map löschen, Skalar setzen. Für die
    (ganzheitliche) Bewegungs-Schritt-Einlagerung, damit eine vorher verteilte Charge
    wieder konsistent an einem Ort steht."""
    inst.location_type = location_type
    inst.location_id = int(location_id)
    inst.place = None
    inst.locations = None


def set_place(inst: Instance, place: dict) -> None:
    """Ganze Instanz an einen **Ort** (Adresse/GPS, keine Objektnummer). Ein Ort hält immer
    die ganze (Rest-)Menge – eine bestehende Verteilung wird dabei zusammengeführt."""
    inst.location_type = "place"
    inst.location_id = None
    inst.place = place
    inst.locations = None


def place_key(place: dict | None) -> tuple:
    """Vergleichsschlüssel eines Orts (normalisiert) – zwei Orte gelten als derselbe,
    wenn Bezeichnung + Adresse übereinstimmen. Ein Ort hat keine Objektnummer, darum
    ist DAS seine Identität."""
    p = place or {}
    def n(v) -> str:
        return re.sub(r"[^a-z0-9]", "", str(v or "").lower())
    return (n(p.get("name")), n(p.get("street1")), n(p.get("zip")),
            n(p.get("city")), n(p.get("country")))


def is_at(inst: Instance, ltype: str | None, lid: int | None, place: dict | None = None) -> bool:
    """Liegt die Instanz **ausschliesslich** an genau diesem Standort? (Ist↔Soll-Vergleich –
    berücksichtigt den Ort, dessen Identität die Adresse ist, nicht eine Nummer.)"""
    if inst.locations:
        return False          # verteilt → nie «vollständig am Ziel»
    if inst.location_type != ltype:
        return False
    if ltype == "place":
        return place_key(inst.place) == place_key(place)
    return inst.location_id == lid


def set_target(inst: Instance, ltype: str, lid: int | None, place: dict | None = None) -> None:
    """Die GANZE Instanz an einen Standort setzen – die EINE Stelle, die zwischen
    objektbasiertem Halter und Ort unterscheidet."""
    if ltype == "place":
        set_place(inst, place or {})
    else:
        set_single(inst, ltype, int(lid))


def clear(inst: Instance) -> None:
    """Instanz **standortlos** machen (Skalar + Verteilungs-Map löschen). EINE Stelle für
    «kein Halter mehr»: beim Verschrotten verlässt das Teil den Bestand endgültig – ein
    Standort ist immer ein realer Halter (Lagerplatz/Person/Instanz), den Ausschuss nicht
    mehr hat. Der Endzustand ``disposition='scrapped'`` trägt die «Wo»-Aussage."""
    inst.location_type = None
    inst.location_id = None
    inst.locations = None


def move(inst: Instance, to_type: str, to_id: int, qty, from_id: int | None = None) -> None:
    """``qty`` einer (Chargen-)Instanz von einem Quellstandort auf ``to_id`` verlagern.

    Ein Bewegen = ein Task (Variante b): der Rest bleibt, wo er war. Quelle = ``from_id``
    (falls angegeben), sonst die grösste Teilmenge ≠ Ziel. Die Objektnummer bleibt IMMER;
    es entsteht KEINE neue Instanz. Wirft bei ungültiger Menge/Quelle (HTTP 400/409)."""
    if to_type == "place":
        # Ein Ort trägt keine Objektnummer und kann darum nicht Schlüssel der Verteilung
        # sein. Fachlich ist das auch richtig: eine Adresse unterscheidet zwei Plätze am
        # selben Standort nicht («Band A» und «Wareneingang» haben dieselbe Anschrift).
        # Wer eine Teilmenge getrennt führen will, bewegt sie auf eine Behälter-Instanz.
        raise HTTPException(
            400,
            detail="Eine Teilmenge lässt sich nicht auf einen Ort verlagern – ein Ort hält "
                   "immer die ganze Menge. Für Teilmengen eine Behälter-Instanz als Ziel wählen.",
        )
    q = to_qty(qty)
    if q <= 0:
        raise HTTPException(400, detail="Zu verlagernde Menge muss grösser als 0 sein.")
    to_id = int(to_id)
    dist = _seed_from_scalar(inst)
    if not dist:
        raise HTTPException(409, detail="Die Instanz hat keinen Ausgangs-Standort.")

    if from_id is not None:
        src = int(from_id)
        if src not in dist:
            raise HTTPException(400, detail="Am gewählten Quellstandort liegt nichts von dieser Instanz.")
    else:
        candidates = {k: v for k, v in dist.items() if k != to_id}
        if not candidates:
            raise HTTPException(400, detail="Die Instanz liegt bereits vollständig an diesem Standort.")
        src = max(candidates, key=lambda k: candidates[k][1])
    if src == to_id:
        raise HTTPException(400, detail="Quell- und Zielstandort sind identisch.")

    src_type, src_qty = dist[src]
    if q > src_qty:
        raise HTTPException(
            400,
            detail=f"Am Quellstandort liegen nur {src_qty} – bitte weniger verlagern "
                   f"oder den Quellstandort wählen.",
        )
    dist[src] = (src_type, src_qty - q)
    tgt_type, tgt_qty = dist.get(to_id, (to_type, ZERO))
    dist[to_id] = (to_type, tgt_qty + q)
    _write(inst, dist)
