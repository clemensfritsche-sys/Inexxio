"""**Die Aufteilung einer Instanz** – wer hält wie viel, und was ist frei.

Eine Instanz ist eine **Menge**, kein Ding, und ihre Menge ist immer vollständig aufgeteilt:
jeder Anteil gehört genau einem Auftrag oder ist frei. Genau das steht seit jeher in
``instances.reservations`` – nur war es nie sichtbar. Dieses Modul macht es sichtbar, an
EINER Stelle für alle drei Nutzer:

* die **Auswahl** rendert daraus ihre Zeilen (Instanz · Menge · Halter) – und weil man eine
  Zeile anklickt, ist beantwortet, wem man etwas wegnimmt;
* das **Auftrags-Detail** zeigt, dass ein Teil gerade woanders liegt («2 Stk → Auftrag …»);
* das **Instanz-Detail** zeigt dieselbe Aussage aus der anderen Richtung.

Die Namen der haltenden Aufträge kommen über **eine** Abfrage je Aufruf (kein N+1).
"""

from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.orm import Session

from ..models import Article, Instance, Order
from ..schemas.instance import InstanceShare
from ..schemas.order import AffectedOrder, AffectedShare
from .quantity import ZERO, to_qty


def shares_for(db: Session, insts: list[Instance]) -> dict[int, list[InstanceShare]]:
    """Die Anteile mehrerer Instanzen auf einmal – ``{instanz_db_id: [Anteil, …]}``.

    Die Liste ist **vollständig**: die gehaltenen Anteile plus der freie Rest. Ein Anteil
    ohne ``order_object_id`` ist der freie; fehlt er, ist die Instanz ganz vergeben.
    Anteile mit Menge 0 tauchen nicht auf."""
    if not insts:
        return {}
    order_ids = {int(k) for i in insts for k in (i.reservations or {})}
    orders = _orders(db, order_ids)
    out: dict[int, list[InstanceShare]] = {}
    for inst in insts:
        rows: list[InstanceShare] = []
        held = ZERO
        for key, qty in (inst.reservations or {}).items():
            q = to_qty(qty)
            if q <= 0:
                continue
            held += q
            o = orders.get(int(key))
            rows.append(InstanceShare(
                order_object_id=(o[0] if o else None), order_name=(o[1] if o else None),
                reason=(o[2] if o else None), quantity=float(q)))
        rest = to_qty(inst.quantity) - held
        if rest > 0:
            # **Der Rest ist nur dann frei, wenn die Instanz am Lager liegt.** Steckt sie
            # noch in ihrem Erzeugungsauftrag (in Arbeit, gesperrt), gehört der unbeanspruchte
            # Teil IHM – er hat ihn hervorgebracht. Sonst zeigte die Auswahl «frei» an einem
            # Stück, das mitten in einem Prozess hängt, und niemand würde gefragt.
            owner = _creator(db, inst, orders)
            rows.append(InstanceShare(
                order_object_id=(owner[0] if owner else None),
                order_name=(owner[1] if owner else None),
                reason=(owner[2] if owner else None), quantity=float(rest)))
        out[inst.id] = rows
    return out


def _creator(db: Session, inst: Instance, cache: dict) -> tuple | None:
    """Der Auftrag, dem der **unbeanspruchte Rest** gehört – der Erzeuger, solange die
    Instanz nicht am Lager liegt. Am Lager gehört der Rest niemandem (= frei)."""
    from .inventory import is_in_stock
    if is_in_stock(inst) or not inst.order_id:
        return None
    if inst.order_id not in cache:
        cache.update(_orders(db, {inst.order_id}))
    return cache.get(inst.order_id)


def _orders(db: Session, ids: set[int]) -> dict[int, tuple[int | None, str | None, str | None]]:
    """``{db_id: (objektnummer, name, grund)}`` – EINE Abfrage für Aufträge und Artikelnamen.

    Der Name kommt aus derselben Ableitung wie überall (``orders.order_display_name``):
    ein Datensatz heisst an jeder Stelle gleich."""
    if not ids:
        return {}
    from .orders import order_display_name
    rows = db.query(Order).filter(Order.id.in_(ids)).all()
    arts = {
        a.id: a.name
        for a in db.query(Article).filter(
            Article.id.in_({o.article_id for o in rows if o.article_id})).all()
    } if rows else {}
    return {o.id: (o.object_id, order_display_name(o, arts.get(o.article_id)), o.reason)
            for o in rows}


def losses(db: Session, inst: Instance, order: Order, want=None) -> dict[int, Decimal]:
    """**Wer verliert wie viel** an dieser Instanz, wenn dieser Auftrag seinen Anspruch
    durchsetzt – ``{auftrag_db_id: menge}``.

    Die Reihenfolge ist die Antwort auf «wer verliert zuerst»:

    1. der **genannte** Anteil (die Zeile, die angeklickt wurde) – ``orders.pick_sources``;
       er verliert **unbedingt**, auch wenn woanders noch etwas frei wäre (#394): der Klick
       sagt, WOHER das Stück kommt, nicht bloss WIE VIEL;
    2. der **freie Rest** deckt, was danach noch offen ist – ohne Verlierer;
    3. der **Erzeuger**, solange die Instanz nicht am Lager liegt (ihm gehört der Rest);
    4. die übrigen Ansprüche, grösster zuerst.

    Ohne genannten Anteil geht darum nur verloren, was **fehlt**: reicht der freie Rest,
    verliert niemand – dann ist die Antwort leer. Das ist derselbe Satz wie «ein freier
    Anteil gehört niemandem», nur in Zahlen.

    **Die Menge zählt, nicht der Auftrag** (Testnotiz #391): wer 2 Stück aus einer 4er-Charge
    nimmt, entzieht 2 – nicht 4, nur weil der Eltern-Auftrag über 4 lautet. Vorher stand in
    der Frage die *Sollmenge des Betroffenen*; das las sich wie ein Totalverlust.

    Nicht laufende Halter zählen für die **Arithmetik** mit (``enforce`` kürzt auch sie),
    erscheinen aber nicht im Ergebnis – gefragt wird nur, wer noch läuft. Rein (schreibt nicht)."""
    from .inventory import is_in_stock
    from .reservation import reserved_for
    # ``want`` = die gewünschte Menge, wenn der Anspruch noch gar nicht steht (die Frage
    # wird auch schon beim Auswählen gestellt, um den Eltern abzuleiten); sonst zählt der
    # gesetzte Anspruch.
    mine = to_qty(want) if want is not None else reserved_for(inst, order.id)
    if mine <= 0:
        return {}
    claims = {int(k): to_qty(v) for k, v in (inst.reservations or {}).items() if int(k) != order.id}
    rest = to_qty(inst.quantity) - sum(claims.values(), ZERO)      # unbeansprucht

    def share_of(oid: int) -> Decimal:
        if oid in claims:
            return claims[oid]
        # Der Erzeuger hält den unbeanspruchten Rest, solange die Instanz nicht am Lager ist.
        return rest if (inst.order_id == oid and not is_in_stock(inst) and rest > ZERO) else ZERO

    out: dict[int, Decimal] = {}
    named = (order.pick_sources or {}).get(str(inst.object_id))
    need = mine
    if named is not None and int(named) != order.id:
        take = min(need, share_of(int(named)))      # **unbedingt** – siehe Docstring
        if take > 0:
            out[int(named)] = take
            need -= take
    # Der freie Rest deckt ohne Verlierer, was danach noch offen ist.
    need -= rest if is_in_stock(inst) and rest > ZERO else ZERO
    ranked: list[int] = []
    if inst.order_id and not is_in_stock(inst):
        ranked.append(inst.order_id)
    ranked += sorted(claims, key=lambda k: -claims[k])
    for oid in ranked:
        if need <= 0:
            break
        if oid == order.id:
            continue
        take = min(need, share_of(oid) - out.get(oid, ZERO))
        if take <= 0:
            continue
        need -= take
        out[oid] = out.get(oid, ZERO) + take
    # Gefragt wird nur, wer noch läuft – für die Arithmetik zählen die anderen mit.
    running = {
        o.id for o in db.query(Order.id).filter(
            Order.id.in_(set(out)), Order.is_active == True, Order.status == "released").all()
    }
    return {k: v for k, v in out.items() if k in running}


class Affected(NamedTuple):
    """Ein betroffener Auftrag: **wer**, **wie viel** und **woher** (Instanz → Menge)."""
    order: Order
    quantity: Decimal
    sources: dict[int, Decimal]


def affected(db: Session, order: Order, insts: list[Instance],
             wanted: dict | None = None) -> list[Affected]:
    """**Wem nimmt diese Auswahl wie viel weg?** – über alle gewählten Instanzen hinweg.

    Die Regel je Instanz steht in ``losses``; hier wird nur zusammengezählt. Die Frage stellt
    sich an ZWEI Stellen – beim Erteilen eines Auftrags (Router) und am gespeicherten Entwurf
    (``orders.to_order_response``) – und wurde dort zweimal verschieden beantwortet: die eine
    Fassung meldete den **Verlust**, die andere, was der Halter überhaupt **hält**. Genau
    dieser Unterschied war Testnotiz #391 («verliert 4», obwohl 2 genommen wurden). Jetzt
    gibt es die Antwort einmal."""
    totals: dict[int, Decimal] = {}
    sources: dict[int, dict[int, Decimal]] = {}
    for i in insts:
        for oid, qty in losses(db, i, order, (wanted or {}).get(i.object_id)).items():
            totals[oid] = totals.get(oid, ZERO) + qty
            sources.setdefault(oid, {})[i.object_id] = qty
    if not totals:
        return []
    rows = {o.id: o for o in db.query(Order).filter(Order.id.in_(totals)).all()}
    out = [Affected(rows[i], q, sources.get(i, {})) for i, q in totals.items() if i in rows]
    return sorted(out, key=lambda a: a.order.object_id or 0)


def affected_rows(db: Session, hits: list[Affected]) -> list[AffectedOrder]:
    """Die betroffenen Aufträge als Datensatz-Zeilen für die Frage (Notizen #387/#391/#393).

    Eine Zeile beantwortet drei Dinge: **wer** verliert (Auftrag – der Name ist der
    Artikelname, darum trägt die Zeile die Datensatzart), **wie viel** (in der Einheit des
    Artikels) und **woher** (aus welcher Instanz)."""
    from .orders import order_display_name
    arts = {a.id: a for a in db.query(Article).filter(
        Article.id.in_({h.order.article_id for h in hits if h.order.article_id})).all()} if hits else {}
    out: list[AffectedOrder] = []
    for h in hits:
        if not h.order.object_id:
            continue
        art = arts.get(h.order.article_id)
        out.append(AffectedOrder(
            object_id=h.order.object_id,
            name=order_display_name(h.order, art.name if art else None),
            reason=h.order.reason, article_name=art.name if art else None,
            unit=art.unit if art else None, quantity=float(h.quantity),
            sources=[AffectedShare(instance_object_id=oid, quantity=float(q))
                     for oid, q in sorted(h.sources.items())],
        ))
    return out


def losers(db: Session, inst: Instance, order: Order, want=None) -> list[Order]:
    """Dieselbe Regel wie ``losses``, nur die **Aufträge** – zwei Formen, eine Regel."""
    hit = losses(db, inst, order, want)
    if not hit:
        return []
    rows = {o.id: o for o in db.query(Order).filter(Order.id.in_(hit)).all()}
    return [rows[i] for i in hit if i in rows]
