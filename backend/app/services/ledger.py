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
    # Rangfolge: der genannte Halter ≻ **freier Bestand** ≻ fremde Halter (grösste zuerst).
    # Ohne die Mittelstufe griffe eine Buchung ohne Quell-Angabe in den Topf eines fremden
    # Auftrags, obwohl daneben freier Bestand liegt – niemand verliert etwas, wenn frei
    # gedeckt werden kann (dieselbe Regel wie ``shares.losses``).
    ranked = sorted(pool.items(),
                    key=lambda kv: (0 if kv[0].holder == prefer_holder
                                    else 1 if kv[0].holder is None else 2, -kv[1]))
    out: list[tuple[Bucket, Decimal]] = []
    left = qty
    for b, have in ranked:
        if left <= 0:
            break
        cut = min(left, have)
        out.append((b, cut))
        left -= cut
    return out


def _moved_units(inst: Instance, qty, holder, given) -> list[int] | None:
    """**Welche Stücke diese Buchung bewegt** – die Nummern, die in die Zeile kommen.

    ``given`` = der Aufrufer nennt sie ausdrücklich. Das ist der Weg für alles, was Stücke
    **entwertet** (verschrottet/verkauft/verbaut): dort sind sie zum Buchungszeitpunkt schon
    aus der Karte verschwunden, nur der Aufrufer weiss noch, welche es waren.

    Sonst wird geschnappt, was der Ziel-Halter gerade **beansprucht** – der Aufrufer hat die
    Stücke unmittelbar davor umgehängt (``reservation._write`` → ``units.sync``), also ist
    das die Antwort für genau diesen Moment. Bewusst nur der Anspruch, nicht der geerbte
    Rest: wer über ``Instance.order_id`` hält, hält *alles*, und das wäre für eine einzelne
    Buchung viel zu breit. Findet sich kein Anspruch, bleibt die Zeile leer statt zu raten."""
    if given is not None:
        return [int(n) for n in given] or None
    if holder is None or holder == KEEP or not inst.object_id:
        return None
    from . import units as U
    from .quantity import to_qty
    rows, want, out = U.of(inst, holder=holder), to_qty(qty), []
    for u in rows:
        if want <= 0:
            break
        out.append(u.index)
        want -= u.quantity
    return out or None


def post(db: Session | None, inst: Instance, qty, *, kind: str,
         holder: Optional[int] = None, quality: str | None = None,
         disposition: str | None = None, src_holder: Optional[int] = "?",
         src_disposition: str | None = None, units: list | None = None,
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
            units=_moved_units(inst, q, holder, units), note=note))
        return
    _ensure_opening(db, inst)
    # Erst schreiben lassen, dann lesen: der Kontostand ist eine DB-Abfrage – eben erst
    # ge-`add`-ete Zeilen (Eröffnung, vorherige Buchung derselben Anfrage) muss sie sehen,
    # sonst bucht der Drain gegen einen leeren Stand (dieselbe Lehre wie Testnotiz #392).
    db.flush()
    balances = lots(db, inst)
    prefer = src_holder if src_holder != "?" else (holder if holder != KEEP else None)
    sources = _drain(balances, q, prefer, src_disposition)
    # **Die Nummern EINMAL bestimmen** – sie gelten für diese Buchung als Ganzes und werden
    # auf die (ggf. mehreren) Quell-Töpfe der Reihe nach verteilt.
    moved = list(_moved_units(inst, q, (None if holder == KEEP else holder), units) or ())
    covered = ZERO
    for b, amt in sources:
        db.add(MaterialMove(
            instance_object_id=inst.object_id, article_id=inst.article_id, actor_id=actor_id,
            kind=kind, quantity=amt,
            src_order_id=b.holder, src_quality=b.quality, src_disposition=b.disposition,
            dst_order_id=(b.holder if holder == KEEP else holder),
            dst_quality=quality or b.quality,
            dst_disposition=disposition or b.disposition,
            units=(moved[:int(amt)] or None), note=note))
        del moved[:int(amt)]
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


#: Buchungen, die eine Menge **zurückgeben** – nach oben an den Verleiher oder ans Lager.
#: Ein ``taken`` gehört NICHT dazu: das reicht nach unten weiter (Testnotiz #559).
RETURNING = ("returned", "released")


class Departed(NamedTuple):
    """Eine zurückgegebene Menge – **mit ihren Nummern** (Testnotiz #559)."""
    quantity: Decimal
    units: tuple[int, ...] = ()


def departed_of(db: Session, order_id: int) -> dict[tuple[int, str, str], Departed]:
    """**Was diesen Auftrag ZURÜCKGEGEBEN hat** – je (Instanz, Qualität, Verbleib).

    Die faktische Antwort auf «was kam zurück?»: nicht eine Vorhersage aus dem
    Hineingegangenen, sondern die tatsächlichen Rückgabe-Buchungen, im Zustand, in dem sie
    gingen.

    **Nur echte Rückgaben** (Testnotiz #559). Gezählt wurde jede lebende Abgabe – auch die an
    einen **weiteren** Unter-Auftrag. Ein Abzweig, der 2 Stück übernahm, davon 1 an seine
    eigene Abweichung weitergab (die es verschrottete) und 1 zurückgab, meldete darum «2
    zurück»: die Weitergabe nach unten wurde als Rückgabe nach oben gelesen. Was ein Abzweig
    weiterreicht, hat den Eltern nie wieder erreicht."""
    out: dict[tuple[int, str, str], Departed] = {}
    for m in moves_of(db, order_id):
        if (m.src_order_id == order_id and m.dst_order_id != order_id
                and m.kind in RETURNING
                and (m.dst_disposition or "") not in TERMINAL):
            key = (m.instance_object_id, m.dst_quality or "pending",
                   m.dst_disposition or "in_process")
            cur = out.get(key) or Departed(ZERO)
            # **Die Nummern stehen in der Buchung** – nicht in dem, was der Auftrag einmal
            # übernommen hat: er gibt ja womöglich weniger zurück, als er bekommen hat.
            out[key] = Departed(cur.quantity + to_qty(m.quantity),
                                cur.units + tuple(m.units or ()))
    return out


class ViewRow(NamedTuple):
    """Eine Materialzeile aus Sicht EINES Auftrags – roh, ohne Anzeige-Meta."""
    instance_object_id: int
    quality: str
    disposition: str
    quantity: Decimal
    reserved: bool               # gehalten UND am Lager = gebunden
    at: object | None            # Zeitpunkt (nur terminal/abgegeben – Vergangenheit)
    # Wohin eine ABGEGEBENE Menge ging (DB-id des Auftrags; ``None`` = ans Lager bzw. die
    # Zeile ist gehalten/terminal). Die Fluss-Achse filtert damit: was in einen Abzweig
    # ging, liegt unterhalb seiner Teilung in DESSEN Spur – nicht mehr auf der Achse.
    to_order: int | None = None
    # **Welche Stücke** – die Nummern DIESER Buchung (``[1, 2]`` = ``…-1``/``…-2``). Sie
    # stehen im Journal, nicht in der heutigen Karte: darum bleibt eine durchlaufene Kante
    # richtig, auch wenn ein Abzweig später alles zurückgibt (#543/#544). Leer = Altbestand
    # ohne aufgezeichnete Nummern → der Leser fällt auf die Ableitung zurück.
    units: tuple[int, ...] = ()


class OrderView(NamedTuple):
    """Die drei Zeilenarten der Auftrags-Achse – getrennt, damit jede Sicht die richtigen
    nimmt: die volle Achse alle drei, der Bypass nur gehalten+terminal (was HIER ist)."""
    held: list[ViewRow]          # noch in der Obhut dieses Auftrags
    terminal: list[ViewRow]      # von ihm ausgesteuert (verschrottet/verkauft/verbaut)
    departed: list[ViewRow]      # abgegeben (ans Lager oder einen anderen Auftrag)

    @property
    def material(self) -> list[ViewRow]:
        return self.held + self.terminal + self.departed


def order_view(db: Session, order_id: int) -> OrderView | None:
    """**Die Achse eines Auftrags aus dem Journal.** ``None`` = der Auftrag hat keine
    Buchungen (Altbestand → Legacy-Ableitung).

    Die eine Regel: **alles, was je in diesen Auftrag hineingebucht wurde, ist genau einmal
    da** – als noch gehaltener Topf, als terminaler Topf (ihm zugeschrieben, mit Zeitpunkt)
    oder als abgegebene Menge (im Zustand, in dem sie ging, mit Zeitpunkt). Kein
    ``held_quantity``, keine Links-Menge, keine Reservierungs-Map: eine Quelle.

    Damit löst sich die frühere Arithmetik der Oberfläche von selbst auf: der Bypass neben
    einem Abzweig IST gehalten+terminal (der Abzweig hat seinen Anteil ja **weggebucht**),
    und was zurückkam, steht wieder in den Töpfen – nichts wird subtrahiert oder addiert."""
    moves = moves_of(db, order_id)
    if not moves:
        return None
    bal: dict[tuple[int, str, str], Decimal] = {}
    term_at: dict[tuple[int, str, str], object] = {}
    departed: list[ViewRow] = []

    def bucket(oid: int, q: str | None, d: str | None) -> tuple[int, str, str]:
        return (oid, q or "pending", d or "in_process")

    def consume_departed(oid: int, amt: Decimal, src: int | None,
                         units: tuple = ()) -> None:
        """Kommt eine Menge ZURÜCK, verzehrt sie ihre Abgabe-Zeile – sonst stünde sie
        doppelt da (als «abgegeben» UND wieder als gehalten).

        **Und zwar IHRE** (Testnotiz #555): verzehrt wurde bisher die älteste Abgabe
        derselben Instanz, egal an wen. Bei zwei parallelen Abweichungen an derselben Charge
        frass die Rückgabe der einen die Abgabe der anderen – die Achse behauptete danach,
        das Stück liege noch beim falschen Abzweig, und zwei Zeilen trugen dieselbe Nummer.
        Wer zurückgibt, steht in der Buchung; nur wenn es dazu keine Abgabe gibt (Altbestand),
        wird der Reihe nach verzehrt."""
        gone = set(units)
        for match_src in (True, False):
            for i, r in enumerate(departed):
                if amt <= 0:
                    return
                if r.instance_object_id != oid:
                    continue
                if match_src and (src is None or r.to_order != src):
                    continue
                cut = min(amt, r.quantity)
                amt -= cut
                # **Die Nummern gehen mit der Menge** – sonst nennt eine halb verzehrte
                # Abgabe-Zeile weiterhin Stücke, die längst wieder da sind.
                keep = tuple(u for u in r.units if u not in gone) if gone else r.units
                departed[i] = r._replace(quantity=r.quantity - cut, units=keep)
            departed[:] = [r for r in departed if r.quantity > 0]

    for m in moves:
        amt = to_qty(m.quantity)
        if m.src_order_id == order_id and m.src_disposition is not None:
            k = bucket(m.instance_object_id, m.src_quality, m.src_disposition)
            bal[k] = bal.get(k, ZERO) - amt
        if m.dst_order_id == order_id:
            k = bucket(m.instance_object_id, m.dst_quality, m.dst_disposition)
            bal[k] = bal.get(k, ZERO) + amt
            if k[2] in TERMINAL:
                term_at[k] = m.at
            if m.src_order_id != order_id:
                consume_departed(m.instance_object_id, amt, m.src_order_id,
                                 tuple(m.units or ()))
        if (m.src_order_id == order_id and m.dst_order_id != order_id
                and (m.dst_disposition or "") not in TERMINAL):
            # Der Zustand gehört zum MATERIAL, nicht zum Betrachter (#495): ging es in die
            # Obhut eines anderen Auftrags, ist es dort gebunden – auch aus dieser Sicht.
            bound = m.dst_order_id is not None and (m.dst_disposition or "") == "in_stock"
            departed.append(ViewRow(m.instance_object_id, m.dst_quality or "pending",
                                    m.dst_disposition or "in_process", amt, bound, m.at,
                                    m.dst_order_id, tuple(m.units or ())))

    # Die Nummern der terminalen Buchungen: sie sind aus der Karte entwertet und stehen
    # **nur noch im Journal** – ohne sie könnte eine verschrottete Menge ihre Stücke nie
    # mehr benennen.
    term_units: dict[tuple, tuple] = {}
    for m in moves:
        if m.dst_order_id == order_id and (m.dst_disposition or "") in TERMINAL and m.units:
            k = bucket(m.instance_object_id, m.dst_quality, m.dst_disposition)
            term_units[k] = term_units.get(k, ()) + tuple(m.units)

    held: list[ViewRow] = []
    terminal: list[ViewRow] = []
    for (oid, q, d), v in sorted(bal.items()):
        if v <= 0:
            continue
        if d in TERMINAL:
            terminal.append(ViewRow(oid, q, d, v, False, term_at.get((oid, q, d)),
                                    None, term_units.get((oid, q, d), ())))
        else:
            held.append(ViewRow(oid, q, d, v, d == "in_stock", None))
    return OrderView(held, terminal, departed)


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
