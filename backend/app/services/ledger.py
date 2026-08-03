"""**Das Material-Journal – die EINE Schreibstelle für «was ist passiert»** (ADR 007).

Bestand ist ein Konto, jede Veränderung eine Buchung, Buchungen sind unveränderlich.
Eine Menge einer Instanz ist zu jedem Zeitpunkt in genau einem **Topf**
``(Halter · Qualität · Verbleib)``; jedes fachliche Ereignis bewegt eine Menge von Topf zu
Topf. Daraus folgen die drei Fragen des Nutzers ohne weitere Regeln:

    Passiert     = die Zeilen (``material_moves``), chronologisch, append-only.
    Jetzt        = der Kontostand (``lots``) – der Zustand hängt an der MENGE im Topf,
                   nicht an der Instanz. Damit löst sich das Chargen-Problem im Modell
                   statt in der Anzeige.
    Als Nächstes = der Plan (Schritte) – steht woanders, denn er darf sich ändern.

**Buchhaltung ist streng, Zuordnung ist tolerant:** eine Buchung entnimmt ihrem Quell-Topf
nie mehr, als er hält – reicht er nicht, deckt sie aus den übrigen lebenden Töpfen der
Instanz (bevorzugt derselbe Halter). Was dann noch fehlt, wird als sichtbar markierte
Korrektur gebucht (``note='!unbalanced'``) statt still zu verschwinden; ``verify_instance``
findet solche Stellen. Sie sind Bugs im Aufrufer, keine Kontokorruption.

**Eröffnungsbilanz statt Migration:** Alt-Instanzen bekommen keine nachgerechnete Historie
(die wäre gelogen). Vor der ersten Buchung schreibt ``_ensure_opening`` ihren aktuellen
Stand als ``opening`` – ab dort ist die Geschichte vollständig.
"""

from decimal import Decimal
from typing import NamedTuple, Optional

from sqlalchemy.orm import Session, object_session

from ..models import Instance, MaterialMove
from .quantity import ZERO, to_qty

# Terminale Verbleibe: aus diesen Töpfen kommt nichts mehr heraus.
TERMINAL = ("scrapped", "sold", "consumed")

KINDS = ("created", "opening", "taken", "returned", "released",
         "sold", "consumed", "scrapped", "blocked", "unblocked")

# Sentinel für ``post(holder=KEEP)``: der Halter bleibt, wie er im Quell-Topf war –
# für reine Zustandswechsel (sperren/entsperren), die niemandem etwas wegnehmen.
KEEP = "keep"


class Bucket(NamedTuple):
    """Ein Topf: wem gehört die Menge (Auftrag oder niemand) und in welchem Zustand ist sie."""
    holder: Optional[int]        # Order.id | None = frei
    quality: str                 # pending | passed | blocked
    disposition: str             # in_process | in_stock | consumed | sold | scrapped


def _projected_lots(inst: Instance) -> dict[Bucket, Decimal]:
    """Der heutige Stand einer Instanz aus den **Projektionen** (Skalar + Reservierungs-Map)
    – die Eröffnungsbilanz für Alt-Instanzen, dieselbe Leseregel wie ``shares``: Ansprüche
    je Halter, der Rest frei (am Lager) bzw. beim Erzeuger (im Prozess)."""
    q, d = inst.quality or "pending", inst.disposition or "in_process"
    total = to_qty(inst.quantity)
    out: dict[Bucket, Decimal] = {}
    held = ZERO
    for key, val in (inst.reservations or {}).items():
        amt = to_qty(val)
        if amt <= 0:
            continue
        amt = min(amt, total - held)
        if amt <= 0:
            break
        out[Bucket(int(key), q, d)] = out.get(Bucket(int(key), q, d), ZERO) + amt
        held += amt
    rest = total - held
    if rest > 0:
        # Am Lager gehört der Rest niemandem; im Prozess hält ihn der Erzeuger.
        holder = None if d == "in_stock" else inst.order_id
        out[Bucket(holder, q, d)] = out.get(Bucket(holder, q, d), ZERO) + rest
    return out


def _ensure_opening(db: Session, inst: Instance) -> None:
    """Vor der ersten Buchung: den heutigen Stand als Eröffnung festhalten."""
    if not inst.object_id:
        return
    has = db.query(MaterialMove.id).filter(
        MaterialMove.instance_object_id == inst.object_id).first()
    if has:
        return
    for b, qty in _projected_lots(inst).items():
        db.add(MaterialMove(
            instance_object_id=inst.object_id, article_id=inst.article_id,
            kind="opening", quantity=qty,
            dst_order_id=b.holder, dst_quality=b.quality, dst_disposition=b.disposition))


def lots(db: Session, inst: Instance, *, up_to_id: int | None = None) -> dict[Bucket, Decimal]:
    """**Der Kontostand** – die Summe der Buchungen je Topf. ``up_to_id`` liefert den Stand
    von damals (as-of): die Vergangenheit ist eine Abfrage, keine Rekonstruktion."""
    if not inst.object_id:
        return {}
    q = db.query(MaterialMove).filter(MaterialMove.instance_object_id == inst.object_id)
    if up_to_id is not None:
        q = q.filter(MaterialMove.id <= up_to_id)
    out: dict[Bucket, Decimal] = {}
    for m in q.order_by(MaterialMove.id).all():
        amt = to_qty(m.quantity)
        # Eine Buchung HAT eine Quelle, ausser sie erschafft (created/opening: src alles NULL).
        if m.src_disposition is not None:
            src = Bucket(m.src_order_id, m.src_quality or "pending", m.src_disposition)
            out[src] = out.get(src, ZERO) - amt
        dst = Bucket(m.dst_order_id, m.dst_quality or "pending", m.dst_disposition or "in_process")
        out[dst] = out.get(dst, ZERO) + amt
    return {b: v for b, v in out.items() if v > 0}


def _drain(balances: dict[Bucket, Decimal], qty: Decimal, prefer_holder: Optional[int],
           from_disposition: str | None = None) -> list[tuple[Bucket, Decimal]]:
    """Aus welchen Töpfen die Menge kommt: bevorzugt derselbe Halter, dann die übrigen
    lebenden Töpfe (grösste zuerst). Terminale Töpfe geben nie etwas her – ausser der
    Aufrufer nennt sie ausdrücklich (``from_disposition='sold'``: die Retoure ist der eine
    legitime Weg aus «verkauft» zurück)."""
    if from_disposition is not None:
        pool = {b: v for b, v in balances.items() if b.disposition == from_disposition}
    else:
        pool = {b: v for b, v in balances.items() if b.disposition not in TERMINAL}
    ranked = sorted(pool.items(),
                    key=lambda kv: (0 if kv[0].holder == prefer_holder else 1, -kv[1]))
    out: list[tuple[Bucket, Decimal]] = []
    left = qty
    for b, have in ranked:
        if left <= 0:
            break
        cut = min(left, have)
        out.append((b, cut))
        left -= cut
    return out


def post(db: Session | None, inst: Instance, qty, *, kind: str,
         holder: Optional[int] = None, quality: str | None = None,
         disposition: str | None = None, src_holder: Optional[int] = "?",
         src_disposition: str | None = None,
         actor_id: int | None = None, note: str | None = None) -> None:
    """**Eine Buchung** – Menge ``qty`` der Instanz wandert in den Ziel-Topf.

    ``quality``/``disposition`` leer = der Zustand bleibt, wie er im Quell-Topf war (reiner
    Halterwechsel). ``src_holder`` nennt, aus wessen Anteil es kommt (``"?"`` = ableiten:
    bevorzugt der Ziel-Halter selbst, sonst die grössten lebenden Töpfe);
    ``src_disposition`` nennt den Quell-Zustand ausdrücklich (nur so kommt etwas aus einem
    terminalen Topf – die Retoure aus «verkauft»).

    ``db=None`` ist erlaubt (Aufrufer ohne Session-Parameter): die Session kommt dann von
    der Instanz selbst."""
    db = db or object_session(inst)
    q = to_qty(qty)
    if db is None or q <= 0 or not inst.object_id:
        return
    if kind == "created":
        # Entstehen hat keine Vergangenheit – hier gibt es nichts zu eröffnen.
        db.add(MaterialMove(
            instance_object_id=inst.object_id, article_id=inst.article_id, actor_id=actor_id,
            kind=kind, quantity=q, dst_order_id=holder,
            dst_quality=quality or "pending", dst_disposition=disposition or "in_process",
            note=note))
        return
    _ensure_opening(db, inst)
    balances = lots(db, inst)
    prefer = src_holder if src_holder != "?" else (holder if holder != KEEP else None)
    sources = _drain(balances, q, prefer, src_disposition)
    covered = ZERO
    for b, amt in sources:
        db.add(MaterialMove(
            instance_object_id=inst.object_id, article_id=inst.article_id, actor_id=actor_id,
            kind=kind, quantity=amt,
            src_order_id=b.holder, src_quality=b.quality, src_disposition=b.disposition,
            dst_order_id=(b.holder if holder == KEEP else holder),
            dst_quality=quality or b.quality,
            dst_disposition=disposition or b.disposition, note=note))
        covered += amt
    if covered < q:
        # Mehr bewegt, als die Instanz hielt – sichtbar markieren statt still verschlucken.
        db.add(MaterialMove(
            instance_object_id=inst.object_id, article_id=inst.article_id, actor_id=actor_id,
            kind=kind, quantity=q - covered,
            dst_order_id=(None if holder == KEEP else holder),
            dst_quality=quality or (inst.quality or "pending"),
            dst_disposition=disposition or (inst.disposition or "in_process"),
            note="!unbalanced"))


def history(db: Session, inst: Instance) -> list[MaterialMove]:
    """**Was mit diesem Stück passiert ist** – chronologisch, unveränderlich."""
    if not inst.object_id:
        return []
    return (db.query(MaterialMove)
            .filter(MaterialMove.instance_object_id == inst.object_id)
            .order_by(MaterialMove.id).all())


def moves_of(db: Session, order_id: int) -> list[MaterialMove]:
    """Alle Buchungen, an denen dieser Auftrag beteiligt ist (als Quelle oder Ziel)."""
    return (db.query(MaterialMove)
            .filter((MaterialMove.src_order_id == order_id)
                    | (MaterialMove.dst_order_id == order_id))
            .order_by(MaterialMove.id).all())


def departed_of(db: Session, order_id: int) -> dict[tuple[int, str, str], Decimal]:
    """**Was diesen Auftrag lebend verlassen hat** – je (Instanz, Qualität, Verbleib). Das
    ist die faktische Antwort auf «was kam zurück?»: nicht eine Vorhersage aus dem
    Hineingegangenen, sondern die tatsächlichen Rückgabe-Buchungen (returned/released an
    Lager oder Eltern), im Zustand, in dem sie gingen."""
    out: dict[tuple[int, str, str], Decimal] = {}
    for m in moves_of(db, order_id):
        if (m.src_order_id == order_id and m.dst_order_id != order_id
                and (m.dst_disposition or "") not in TERMINAL):
            key = (m.instance_object_id, m.dst_quality or "pending",
                   m.dst_disposition or "in_process")
            out[key] = out.get(key, ZERO) + to_qty(m.quantity)
    return out


def verify_instance(db: Session, inst: Instance) -> list[str]:
    """Drift-Wächter: stimmt der Kontostand mit den Projektionen überein? Liefert Befunde
    (leer = konsistent). Meldet auch markierte Korrekturen (``!unbalanced``)."""
    finds: list[str] = []
    if not inst.object_id:
        return finds
    bal = lots(db, inst)
    if not bal and not db.query(MaterialMove.id).filter(
            MaterialMove.instance_object_id == inst.object_id).first():
        return finds   # noch kein Journal – Alt-Instanz, nichts zu prüfen
    live = sum((v for b, v in bal.items() if b.disposition not in TERMINAL), ZERO)
    if live != to_qty(inst.quantity):
        finds.append(f"Instanz {inst.object_id}: Journal lebend {live} ≠ Projektion {inst.quantity}")
    bad = db.query(MaterialMove).filter(
        MaterialMove.instance_object_id == inst.object_id,
        MaterialMove.note == "!unbalanced").count()
    if bad:
        finds.append(f"Instanz {inst.object_id}: {bad} unbalancierte Buchung(en)")
    return finds
