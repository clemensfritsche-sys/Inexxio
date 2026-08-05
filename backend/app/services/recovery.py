"""Unterdeckung: **eine Frage, die sich selbst beantwortet.**

Ein Auftrag ist unterdeckt, wenn sein Soll nicht (mehr) gesichert ist – weil eine
reservierte Instanz ausgesteuert wurde, weil ein Erzeugungsauftrag Ausschuss hatte oder
weil ein Stück gerade in einer offenen **Abweichung** in Klärung ist.

**Entschieden wird automatisch** (Testnotiz #556). Die Frage hat nämlich nur dann zwei
mögliche Antworten, wenn man sie zu früh stellt – und genau das tat sie:

    Die Menge kommt zurück   → der Auftrag **wartet**, und dabei ruht er ohnehin.
                               Es gibt nichts zu entscheiden, es läuft ja jemand daran.
    Sie kommt NICHT zurück   → sie ist endgültig weg. Dann **sinkt das Soll** auf das
                               Gesicherte (``confirm_quantity``), und der Auftrag läuft
                               mit weniger normal zu Ende.

Welcher der beiden Fälle vorliegt, weiss das System besser als der Mensch: es sieht, ob
noch ein Unter-Auftrag die Menge hält (``supply.covering_sub_orders``). Darum entscheidet
``auto_resolve`` – aufgerufen an der einen Stelle, an der sich das ändern kann.

**Bewusst zurückgestellt (Backlog):** «Ersetzen» (``cover_shortfall`` – der Weg existiert
weiter, es fragt nur niemand mehr danach) und der **Verkauf**: eine bereits bezahlte
Position darf nicht stillschweigend schrumpfen, dafür gibt es die Retoure/Gutschrift
(``sale``-Kredit-Modus mit Stripe-Refund). Bis das gebaut ist, bleibt ein bezahlter Verkauf
mit Fehlmenge stehen, statt automatisch gekürzt zu werden.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from . import process
from .admin import log_audit
from .events import emit
from . import inventory
from .inventory import allocate, fifo_candidates, ready_qty
from .quantity import ZERO, qty_sum, to_qty
from .reservation import free_qty, reserve, reserved_for
from .subject import record_link


def _record_at_step(db: Session, order: Order, article_id: int, event_type: str,
                    payload: dict, actor_id: int) -> None:
    """Die Entscheidung an dem Schritt vermerken, an dem sie gefallen ist.

    **Was passiert ist, muss im Ablauf stehen** (Notiz #281): dass eine Fehlmenge ersetzt
    oder die Menge angepasst wurde, ist die eigentliche Geschichte des Auftrags – ohne
    Spur sieht man später nur noch das Ergebnis und nicht, wie es dazu kam. Die Spur ist
    kein neues Feld, sondern der **Event-Strom**; sie trägt lediglich die Schritt-id, damit
    der Ablauf sie an ihrer Stelle zeigen kann (``OrderStepInfo.resolutions``)."""
    emit(db, event_type, object_type="order", object_id=order.object_id,
         payload={**payload, "article_id": article_id,
                  "step_id": process.blocked_step_for_article(db, order, article_id)},
         actor_id=actor_id)


def is_replaceable(db: Session, order: Order, is_subject: bool) -> bool:
    """**Ist dem Auftrag egal, WELCHES Stück es ist?** – die eine Frage hinter «Ersetzen».

    Ein frisches Stück ist nur dann ein Ersatz, wenn das Fehlende **keine Geschichte** in
    diesem Auftrag hat. Zwei Wege, wie es eine bekommt, und beide zählen:

    * der Auftrag hat es **selbst hervorgebracht** (Erzeugung) – man ersetzt nicht, was man
      gerade herstellt; man stellt weniger her oder wartet;
    * ein Schritt hat **schon daran gearbeitet** – steht der Ablauf bei Schritt 3, hat ein
      frisches Stück die Schritte 1–2 nie durchlaufen und ist damit kein gleichwertiger
      Ersatz, sondern ein anderes Teil.

    **Material** (Ressourcen-Zeile) ist immer austauschbar: der Auftrag braucht *fünf
    Schrauben*, nicht *diese fünf*. Ebenso ein reiner Lager-Zugriff, an dem noch nichts
    getan wurde (Verkauf ab Lager, Bewegung) – dem Kunden sind fünf Schrauben egal, solange
    es fünf sind.

    EINE Ableitung statt einer Fallunterscheidung je Auftragsart. Rein (schreibt nicht)."""
    from .subject import subject_kind
    if not is_subject:
        return True                                   # Material – austauschbar
    return (subject_kind(db, order) != "produce"
            and not any(s["state"] == "done" for s in process.build_order_steps(db, order)))


def _fifo_cover(db: Session, order: Order, article_id: int, need,
                used: list[int] | None = None) -> Decimal:
    """``need`` (Menge) des Artikels aus **freiem** Lagerbestand FIFO für den Auftrag
    reservieren (+ als Subjekt markieren). Liefert die tatsächlich gedeckte Menge und
    sammelt in ``used``, WELCHE Instanzen eingesprungen sind (für die Spur im Ablauf).

    **Ein Stück, das der Auftrag ohnehin schon hält, ist kein Ersatz** (Notiz #403): deckt
    FIFO aus der freien Restmenge DERSELBEN Charge, ändert sich für den Auftrag physisch
    nichts – dieselbe Instanz, dieselbe Nummer. Nur wirklich **neue** Instanzen kommen in
    die Spur; die Zeile «N ab Lager ersetzt» erschien sonst, obwohl gar nichts getauscht
    wurde."""
    covered = ZERO
    cands = fifo_candidates(db, article_id, for_order_id=None, lock=True)   # nur freie Restmengen
    for cand, take in zip(cands, allocate(need, [ready_qty(c) for c in cands])):
        if take <= 0:
            continue
        was_mine = reserved_for(cand, order.id) > 0
        reserve(cand, order.id, take)
        cand.subject_of_order_id = order.id
        record_link(db, cand.object_id, order.id, take)
        if used is not None and cand.object_id and not was_mine:
            used.append(cand.object_id)
        covered += take
    return covered


def _cover_from_stock(db: Session, order: Order, instance_object_ids: list[int] | None,
                      used: dict[int, list[int]] | None = None) -> dict[int, Decimal]:
    """Soviel der offenen **Subjekt**-Fehlmenge wie möglich aus vorhandenem Lagerbestand
    decken. Ohne ``instance_object_ids`` → FIFO über den freien Bestand; mit Auswahl → genau
    diese freigegebenen & freien Instanzen. Liefert die gedeckte Menge je Artikel."""
    short = process.subject_shortfalls(db, order)
    if not short:
        return {}
    covered: dict[int, Decimal] = {}
    if instance_object_ids:
        chosen = list(dict.fromkeys(instance_object_ids))
        # Row-Lock auch im «bestimmte Instanz wählen»-Pfad – wie in JEDEM anderen
        # Allokations-Schreibpfad (``fifo_candidates(lock=True)``). Ohne Sperre ist
        # ``free_qty``-Prüfung + ``reserve`` ein Check-then-Act: zwei gleichzeitige
        # Deckungen derselben Instanz reservieren doppelt (Überverkauf).
        rows = {
            i.object_id: i for i in db.query(Instance).filter(
                Instance.object_id.in_(chosen), Instance.is_active == True)
            .with_for_update().all()
        }
        for oid in chosen:
            inst = rows.get(oid)
            if not inst:
                raise HTTPException(400, detail=f"Instanz {oid} wurde nicht gefunden")
            rem = short.get(inst.article_id, ZERO)
            if rem <= 0:
                raise HTTPException(400, detail=f"Instanz {oid} passt zu keinem offenen Bedarf dieses Auftrags")
            if not inventory.is_in_stock(inst):
                raise HTTPException(409, detail=f"Instanz {oid} ist nicht freigegeben/am Lager")
            take = min(ready_qty(inst), rem)
            if take <= 0:
                raise HTTPException(409, detail=f"Instanz {oid} ist bereits reserviert")
            reserve(inst, order.id, take)
            inst.subject_of_order_id = order.id
            record_link(db, inst.object_id, order.id, take)
            short[inst.article_id] = rem - take
            covered[inst.article_id] = covered.get(inst.article_id, ZERO) + take
            if used is not None:
                used.setdefault(inst.article_id, []).append(oid)
    else:
        for aid, need in short.items():
            picked: list[int] = []
            got = _fifo_cover(db, order, aid, need, picked)
            if got > 0:
                covered[aid] = covered.get(aid, ZERO) + got
                if used is not None:
                    used.setdefault(aid, []).extend(picked)
    return covered


def cover_shortfall(db: Session, order: Order, actor_id: int,
                    instance_object_ids: list[int] | None = None) -> dict:
    """**«Ersetzen»** – die Fehlmenge decken, egal woher.

    EIN Weg statt zweier Knöpfe: erst der **freie Lagerbestand** (FIFO bzw. gezielt gewählte
    Instanzen), für den Rest ein **Nachschub**-Unter-Auftrag (produzieren/beschaffen,
    rekursiv über die Stückliste). Ob das eine, das andere oder beides greift, ist eine
    Verfügbarkeitsfrage – der Mensch entscheidet nur, DASS ersetzt werden soll.

    Deckt auch den reinen **Komponenten**-Bedarf ab (Ressource): dort gibt es keinen
    Subjekt-Lagerweg, ``ensure_supply`` übernimmt ihn vollständig. Committet NICHT."""
    from .supply import ensure_supply
    used: dict[int, list[int]] = {}
    covered = _cover_from_stock(db, order, instance_object_ids, used)
    # Die Spur entsteht VOR dem Nachschub: danach ist der Schritt womöglich nicht mehr
    # blockiert und liesse sich nicht mehr zuordnen. Sie nennt **welche** Instanzen
    # eingesprungen sind – sonst stünde später nur «gedeckt», ohne womit.
    for aid, qty in covered.items():
        # Kam alles aus Instanzen, die der Auftrag ohnehin hielt, war es kein Ersatz –
        # dann steht auch keine Ersatz-Zeile im Ablauf (Notiz #403).
        if not used.get(aid):
            continue
        _record_at_step(db, order, aid, "order.covered_from_stock",
                        {"quantity": qty, "instances": used[aid]}, actor_id)
    created = ensure_supply(db, order, actor_id)
    total = qty_sum(covered.values())
    if total <= 0 and not created:
        raise HTTPException(409, detail="Nichts zu decken – der Bedarf ist bereits gedeckt")
    if total > 0:
        log_audit(db, "orders", None, f"{total} Stück aus Lager gedeckt", actor_id,
                  object_id=order.object_id)
    return {"covered": total, "supply_object_ids": [o.object_id for o in created]}


def _remaining_quantities(db: Session, order: Order, short: dict) -> dict[int, Decimal]:
    """Was von jeder Position übrig bliebe, wenn die Fehlmenge abgezogen wird
    ({article_id: rest}) – der Rest kann 0 oder negativ sein."""
    from .order_lines import lines_for
    if order.article_id:
        return {order.article_id: to_qty(order.quantity or 0) - short.get(order.article_id, ZERO)}
    return {l.article_id: to_qty(l.quantity) - short.get(l.article_id, ZERO) for l in lines_for(db, order)}


def confirm_quantity(db: Session, order: Order, actor_id: int, into: Order | None = None) -> dict:
    """**«Auftragsmenge reduzieren»** – der Auftrag wird mit weniger fertig.

    Das Soll sinkt auf das **Gesicherte**: aus «5 bestellt, 1 in Klärung» wird «4 bestellt».
    Der blockierte Schritt ist damit frei und der Auftrag läuft normal zu Ende – ohne dass
    jemand Ersatz beschaffen muss, den niemand haben will. Die Kürzung wird je Position
    vorgenommen (Einzel-Artikel: ``order.quantity``; Mehrpositionen: die Positionsmenge).

    **Bleibt NICHTS übrig, IST das der Abbruch.** Ein Auftrag, dem alles entzogen wurde, hat
    kein Soll mehr – er auf 0 zu kürzen wäre die umständliche Schreibweise für «abgebrochen».
    Darum gibt es dafür keinen vierten Knopf und keinen Sonder-Dialog mehr: dieselbe
    Entscheidung, deren Konsequenz mit dem Rest skaliert (``deviation.abort_parent``, ``into``
    = der Auftrag, der ihn fortführt). Das ersetzt den früheren «Abbrechen»-Knopf im
    Auftragskopf – ein Weg weniger für dieselbe Sache (Testnotiz #366).

    **Nicht bei bezahlter Ware:** eine Position, deren Verkauf schon bezahlt ist, darf hier
    nicht stillschweigend schrumpfen – das wäre eine Kürzung ohne Gutschrift. Dafür ist die
    Retoure/Erstattung da (``sale``-Kredit-Modus, inkl. Stripe-Refund). Committet NICHT."""
    from .deviation import abort_parent
    from .order_lines import lines_for
    short = process.subject_shortfalls(db, order)
    if not short:
        raise HTTPException(409, detail="Keine Fehlmenge – es gibt nichts zu reduzieren")
    _assert_not_paid(db, order)
    rest_by_article = _remaining_quantities(db, order, short)
    if rest_by_article and all(r <= 0 for r in rest_by_article.values()):
        abort_parent(db, order, into, actor_id)
        return {"aborted": True, "continued_in": into.object_id if into is not None else None}
    changed: dict[int, Decimal] = {}
    if order.article_id:
        rest = rest_by_article[order.article_id]
        _record_at_step(db, order, order.article_id, "order.quantity_confirmed",
                        {"from": to_qty(order.quantity or 0), "to": rest}, actor_id)
        order.quantity = rest
        changed[order.article_id] = rest
    else:
        for line in lines_for(db, order):
            gap = short.get(line.article_id, ZERO)
            if gap <= 0:
                continue
            rest = rest_by_article[line.article_id]
            if rest <= 0:
                raise HTTPException(
                    409, detail="Diese Position hat gar nichts mehr – hier hilft nur «Ersetzen» "
                                "oder die Position zu entfernen.")
            _record_at_step(db, order, line.article_id, "order.quantity_confirmed",
                            {"from": to_qty(line.quantity), "to": rest}, actor_id)
            line.quantity = rest
            changed[line.article_id] = rest
    log_audit(db, "orders", None,
              "Menge bestätigt: " + ", ".join(f"Artikel {a} → {q}" for a, q in changed.items()),
              actor_id, object_id=order.object_id)
    # **Und die Belege gelten für die neue Menge** (Testnotizen #587/#588): eine Offerte über
    # 3 Stück ist keine über 2 – der offene Beleg fällt auf seine erste Stufe zurück, damit
    # die Vereinbarung neu getroffen wird. Der Abbruch-Zweig oben braucht keinen eigenen
    # Aufruf: er läuft über ``cancel_order_effects``, wo dieselbe Funktion die letzte Stufe
    # setzt (storniert). Eine Regel, zwei Enden.
    from .rebase import rebase_documents
    rebase_documents(db, order, actor_id)
    return {"quantities": {a: q for a, q in changed.items()}}


def _assert_not_paid(db: Session, order: Order) -> None:
    """Bezahlte Verkaufspositionen dürfen nicht per Mengenbestätigung schrumpfen – Geld
    zurück geht über die Retoure/Gutschrift, nicht über eine stille Kürzung."""
    from ..models import Sale
    paid = (
        db.query(Sale.id)
        .filter(Sale.order_id == order.id, Sale.is_active == True,
                Sale.kind == "sale", Sale.status == "paid")
        .first()
    )
    if paid:
        raise HTTPException(
            409,
            detail="Bezahlte Position – die Menge wird über eine Retoure/Gutschrift korrigiert, nicht hier.")


def _lost_amounts(db: Session, order: Order) -> dict[int, Decimal]:
    """**Was diesen Auftrag verlassen hat** – je Artikel, aus dem Journal (ADR 007).

    Abgegeben (an einen Abzweig) plus selbst ausgesteuert. Der Unterschied zu einer blossen
    Fehlmenge ist entscheidend: eine Menge, die **nie da war**, ist ein offener Bedarf und
    wird beschafft – eine Menge, die da **war** und weg ist, kommt nicht wieder. Nur die
    zweite darf das Soll senken; sonst kürzte sich ein Auftrag, dessen Nachschub noch gar
    nicht angelegt ist, selbst auf den vorhandenen Bestand."""
    from . import ledger
    if not order.id:
        return {}
    view = ledger.order_view(db, order.id)
    if view is None:
        return {}
    by_oid: dict[int, Decimal] = {}
    for row in list(view.terminal) + list(view.departed):
        by_oid[row.instance_object_id] = by_oid.get(row.instance_object_id, ZERO) + row.quantity
    out: dict[int, Decimal] = {}
    for inst in db.query(Instance).filter(Instance.object_id.in_(by_oid)).all():
        out[inst.article_id] = out.get(inst.article_id, ZERO) + by_oid[inst.object_id]
    return out


def _continued_in(db: Session, order: Order) -> Order | None:
    """Wer hat das Material übernommen? – der jüngste Abzweig dieses Auftrags. Sinkt sein
    Soll auf null, IST das sein Abbruch, und dann will man wissen, wo es weitergeht."""
    return (db.query(Order)
            .filter(Order.parent_order_id == order.object_id, Order.reason == "deviation")
            .order_by(Order.object_id.desc()).first()) if order.object_id else None


def auto_resolve(db: Session, order: Order, actor_id: int | None = None,
                 _seen: set | None = None) -> bool:
    """**Was nicht mehr zurückkommt, reduziert die Menge – von selbst** (Testnotiz #556).

    Die EINE Stelle, an der über eine Fehlmenge entschieden wird. Vorher stand hier eine
    Frage an den Menschen; sie war aber gar keine, sondern eine Ableitung aus etwas, das das
    System ohnehin weiss:

        hält noch jemand die Menge  → nichts tun; der Auftrag wartet und ruht dabei
        hält sie niemand mehr       → sie ist endgültig weg → das Soll sinkt darauf

    Aufgerufen aus ``process.recompute_completion`` – dort, wo sich der Zustand ändert, den
    die Antwort liest: nach jedem Schritt-Abschluss des Auftrags selbst, und über dessen
    Rekursion auch beim Verleiher, sobald ein Abzweig endet. Ein zusätzlicher Auslöser wäre
    eine zweite Wahrheit darüber, wann entschieden wird.

    Liefert ``True``, wenn tatsächlich gekürzt wurde. **Ein bezahlter Verkauf wird nicht
    angetastet** – dort ist die Korrektur eine Gutschrift, keine stille Kürzung; er bleibt
    mit seiner Fehlmenge stehen, bis das gebaut ist (Backlog)."""
    from .supply import covering_sub_orders
    if order.status != "released":
        return False
    short = process.subject_shortfalls(db, order)
    if not short:
        return False
    if covering_sub_orders(db, order):
        return False                       # es kommt noch etwas – warten ist die Antwort
    lost = _lost_amounts(db, order)
    if not any(lost.get(a, ZERO) > 0 for a in short):
        return False                       # war nie da → offener Bedarf, kein Verlust
    try:
        confirm_quantity(db, order, actor_id, into=_continued_in(db, order))
    except HTTPException:
        return False                       # bezahlt: Gutschrift statt Kürzung (Backlog)
    # **Und eine Ebene höher** (Testnotiz #563): wurde dieser Auftrag dadurch abgebrochen,
    # hält ER die Menge seines eigenen Verleihers auch nicht mehr – die Entscheidung fällt
    # dort im selben Moment. So kappt ein Unter-Unter-Auftrag die ganze Kette bis zum
    # Hauptauftrag, ohne dass es dafür eine zweite Regel bräuchte. Zyklensicher.
    seen = _seen or {order.id}
    from .subject import lender_of
    up = lender_of(db, order)
    if up is not None and up.id not in seen:
        auto_resolve(db, up, actor_id, seen | {up.id})
    return True
