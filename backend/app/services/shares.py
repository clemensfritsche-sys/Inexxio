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

from sqlalchemy.orm import Session

from ..models import Article, Instance, Order
from ..schemas.instance import InstanceShare
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


def losers(db: Session, inst: Instance, order: Order, want=None) -> list[Order]:
    """**Wem nimmt der Anspruch dieses Auftrags an dieser Instanz etwas weg?**

    Die Reihenfolge ist die Antwort auf «wer verliert zuerst»:

    1. der **genannte** Anteil (die Zeile, die angeklickt wurde) – ``orders.pick_sources``;
    2. der **Erzeuger**, solange die Instanz nicht am Lager liegt (ihm gehört der Rest);
    3. die übrigen Ansprüche.

    Gefragt wird nur, solange etwas zu verlieren ist: reicht der **freie** Rest für den
    Anspruch, verliert niemand – dann ist die Liste leer. Das ist derselbe Satz wie
    «ein freier Anteil gehört niemandem», nur in Zahlen.

    Rein (schreibt nicht)."""
    from .inventory import is_in_stock
    from .reservation import reserved_for
    # ``want`` = die gewünschte Menge, wenn der Anspruch noch gar nicht steht (die Frage
    # wird auch schon beim Auswählen gestellt, um den Eltern abzuleiten); sonst zählt der
    # gesetzte Anspruch.
    mine = to_qty(want) if want is not None else reserved_for(inst, order.id)
    if mine <= 0:
        return []
    claims = {int(k): to_qty(v) for k, v in (inst.reservations or {}).items() if int(k) != order.id}
    free_before = to_qty(inst.quantity) - sum(claims.values(), ZERO) if is_in_stock(inst) else ZERO
    over = mine - (free_before if free_before > ZERO else ZERO)
    if over <= 0:
        return []                                  # freier Anteil – es verliert niemand
    named = (order.pick_sources or {}).get(str(inst.object_id))
    ranked: list[int] = []
    if named is not None:
        ranked.append(int(named))
    if inst.order_id and not is_in_stock(inst):
        ranked.append(inst.order_id)               # der Erzeuger hält den Rest
    ranked += sorted(claims, key=lambda k: -claims[k])
    rows = {o.id: o for o in db.query(Order).filter(
        Order.id.in_({k for k in ranked if k != order.id}),
        Order.is_active == True, Order.status == "released").all()}
    out: list[Order] = []
    for oid in ranked:
        if over <= 0:
            break
        o = rows.get(oid)
        if o is None or o in out:
            continue
        out.append(o)
        over -= claims.get(oid, to_qty(inst.quantity) - sum(claims.values(), ZERO))
    return out
