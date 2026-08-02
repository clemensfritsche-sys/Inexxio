"""Unterdeckung: **eine Frage, drei Antworten.**

Ein Auftrag ist unterdeckt, wenn sein Soll nicht (mehr) gesichert ist – weil eine
reservierte Instanz ausgesteuert wurde, weil ein Erzeugungsauftrag Ausschuss hatte oder
weil ein Stück gerade in einer offenen **Abweichung** in Klärung ist. Der betroffene
Subjekt-Schritt ist dann «blockiert» (abgeleitet aus dem Bestand, kein stilles
Unterliefern).

Der Mensch beantwortet genau EINE Frage – *was soll mit der Fehlmenge geschehen?* – und es
gibt drei ehrliche Antworten:

1. **Wartet** – kein Knopf, sondern ein **Zustand**: ist die Fehlmenge bereits in einer
   offenen Abweichung oder einem laufenden Nachschub gebunden, ist die Entscheidung längst
   getroffen. Das System sagt nur, worauf gewartet wird (``orders._fill_step_shortfall``).
2. **Ersetzen** (``cover_shortfall``) – EIN Weg statt zweier: was am Lager frei ist, wird
   FIFO reserviert (oder gezielt gewählte Instanzen), und was danach offen bleibt, deckt ein
   **Nachschub**-Unter-Auftrag. Ob produziert oder ab Lager genommen wird, ist eine
   Verfügbarkeitsfrage – keine zweite Entscheidung für den Menschen.
3. **Menge bestätigen** (``confirm_quantity``) – der Auftrag wird mit weniger fertig. Das
   Soll sinkt auf das Gesicherte, der Schritt ist frei, der Auftrag läuft normal zu Ende.
   Fehlte diese Antwort, blieb nur «warten oder ersetzen» – bei einem Erzeugungsauftrag mit
   einem schlechten von fünf Stück beides falsch.

**Geld bleibt ehrlich:** eine bereits **bezahlte** Verkaufsposition lässt sich hier NICHT
kürzen – dafür gibt es die Retoure/Gutschrift (``sale``-Kredit-Modus mit Stripe-Refund).
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Instance, Order
from . import process
from .admin import log_audit
from .events import emit
from . import inventory
from .inventory import allocate, fifo_candidates
from .quantity import ZERO, qty_sum, to_qty
from .reservation import free_qty, reserve
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
    sammelt in ``used``, WELCHE Instanzen eingesprungen sind (für die Spur im Ablauf)."""
    covered = ZERO
    cands = fifo_candidates(db, article_id, for_order_id=None, lock=True)   # nur freie Restmengen
    for cand, take in zip(cands, allocate(need, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        reserve(cand, order.id, take)
        cand.subject_of_order_id = order.id
        record_link(db, cand.object_id, order.id)
        if used is not None and cand.object_id:
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
            take = min(free_qty(inst), rem)
            if take <= 0:
                raise HTTPException(409, detail=f"Instanz {oid} ist bereits reserviert")
            reserve(inst, order.id, take)
            inst.subject_of_order_id = order.id
            record_link(db, inst.object_id, order.id)
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
        _record_at_step(db, order, aid, "order.covered_from_stock",
                        {"quantity": qty, "instances": used.get(aid, [])}, actor_id)
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


def retire_if_subjectless(db: Session, order: Order, into: Order | None, actor_id: int | None) -> bool:
    """**Ein Auftrag auf feste Instanzen, dem nichts mehr bleibt, ist gegenstandslos.**

    Abweichung, Retoure und Bereitstellung beschaffen nichts – sie **behandeln** vorhandene
    Stücke. Nimmt ein anderer Auftrag ihnen diese weg, entsteht keine «Fehlmenge»: es gibt
    schlicht nichts mehr zu behandeln. Darum wird hier auch nichts gefragt – die drei
    Antworten (warten · ersetzen · Menge reduzieren) setzen ein **Soll** voraus, und genau
    das hat ein fixiertes Subjekt nicht (Testnotiz #388: «Keine Fehlmenge – es gibt nichts
    zu reduzieren» kam daher, dass die Antwort trotzdem auf ihn angewandt wurde).

    Bleibt ihm noch eine Teilmenge, läuft er mit weniger weiter – auch das braucht keine
    Frage. Bleibt nichts, wird er **abgebrochen** und zeigt auf den Auftrag, der übernommen
    hat (``into``) – dieselbe Mechanik wie beim Eltern (Testnotiz #366). Committet NICHT."""
    from .deviation import abort_parent
    from .subject import is_fixed_subject, still_holds
    if not is_fixed_subject(order) or order.status != "released":
        return False
    if still_holds(db, order):
        return False
    abort_parent(db, order, into, actor_id)
    return True


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
