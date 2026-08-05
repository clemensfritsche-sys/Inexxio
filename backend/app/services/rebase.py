"""**Ein Beleg gilt für die Menge, für die er ausgestellt wurde** (Testnotizen #587/#588).

Ein Prozessschritt-Modul arbeitet an dem Material, das sein Auftrag schuldet. Ändert sich
diese Grundlage, ist die Vereinbarung, die der Beleg festhält, keine mehr:

    Die Menge sinkt   → der Beleg fällt auf seine **erste Stufe** zurück (``reset``).
                        Eine Offerte über 3 Stück ist keine über 2 – der Lieferant muss
                        neu offerieren, und genau das sagt der Beleg dann auch.
    Die Menge ist weg → der Beleg fällt auf seine **letzte Stufe** (``voided``): storniert.
                        Der Auftrag ist in diesem Moment ohnehin abgebrochen; die Bestellung
                        blieb bisher trotzdem «Angefragt» stehen, und der Lieferant sah eine
                        offene Anfrage für etwas, das es nicht mehr gibt.

**Das ist EINE Regel mit zwei Enden, kein zweiter Mechanismus.** «Menge reduzieren» und
«alles entzogen» sind derselbe Vorgang – nur die Stufe, auf die zurückgefallen wird, ist
eine andere, und die steht in der Registry (``domain/event_types.py``), nicht als if/else
hier. Darum hat diese Funktion auch keinen Modus-Parameter: sie liest am Auftrag ab, welches
Ende gilt.

**Und sie gilt für ALLE Module** – nicht als Aufzählung, sondern weil jeder Schritttyp seine
Stufen selbst deklariert. Wer keine hat, ist nicht ausgenommen: Bewegung, Ressource und
Aussondern schreiben ihre Zeile erst, wenn die Handlung geschehen ist – sie ist damit
Vergangenheit, und die wird nicht umgeschrieben (ADR 007). Aus demselben Grund bleibt auch
ein **erledigter** Beleg unangetastet: eingetroffene Ware ist eingetroffen.

**Selbstheilend statt trigger-abhängig:** die Funktion vergleicht die Menge des Belegs mit
dem heutigen Soll seines Auftrags. Stimmen sie überein, tut sie nichts – sie darf also
beliebig oft laufen, und ein verpasster Aufruf korrigiert sich beim nächsten.
"""

from decimal import Decimal
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Order
from .admin import log_audit
from .events import emit
from .quantity import ZERO, to_qty

#: Die Schritttypen, die überhaupt Stufen haben – **abgeleitet** aus der Registry, nicht
#: gepflegt. Ein neuer Typ mit ``reset``/``voided`` bekommt die Regel damit geschenkt.
STAGED = {k: et for k, et in event_types.REGISTRY.items()
          if et.status_field and (et.reset is not None or et.voided is not None)}


def target_quantities(db: Session, order: Order) -> dict[int, Decimal]:
    """**Das Soll des Auftrags je Artikel** – die Menge, für die seine Belege gelten.

    Dieselbe Quelle, aus der die Belege bei der Freigabe angelegt werden
    (``purchase.instantiate_for_order``/``sale.instantiate_for_order``): die Positionen,
    bzw. beim Einzel-Artikel-Auftrag sein Bedarf. Damit kann die Grundlage eines Belegs gar
    nicht von der abweichen, mit der er entstanden ist."""
    from .order_lines import lines_for
    lines = lines_for(db, order)
    if lines:
        return {l.article_id: to_qty(l.quantity) for l in lines}
    if order.article_id and order.quantity is not None:
        return {order.article_id: to_qty(order.quantity)}
    return {}


def _stage_of(order: Order, et: event_types.EventType):
    """Auf welche Stufe fällt ein Beleg dieses Auftrags zurück? – **abgeleitet**.

    Läuft der Auftrag noch, ist es die erste (die Vereinbarung wird neu getroffen); ist er
    zu Ende, die letzte (es gibt nichts mehr zu vereinbaren). Genau hier – und nur hier –
    unterscheiden sich «reduziert» und «auf null»."""
    return et.reset if (order.status or "") == "released" else et.voided


def _off_basis(order: Order, fact, et: event_types.EventType,
               targets: dict[int, Decimal], stage) -> bool:
    """**Steht dieser Beleg auf einer fremden Grundlage?** – die eine Frage, die beide
    Auslöser stellen (die Automatik und die Bestätigung nach dem Anruf beim Lieferanten).

    Nein, wenn er Vergangenheit ist (erledigt/beendet – eingetroffene Ware ist eingetroffen).
    Sonst entscheidet die **Menge**, nicht die Stufe: ein Beleg, der bereits auf der ersten
    Stufe steht, aber noch die alte Menge trägt, steht sehr wohl auf fremder Grundlage
    (Testnotiz #598 – die Anfrage blieb bei 3 Stück stehen, obwohl der Auftrag nur noch 2
    schuldete, und die Abweichung fiel erst beim Bestellen als «Klärung» auf). Ist der
    Auftrag zu Ende, gibt es gar keine Menge mehr – dann zählt nur, ob die letzte Stufe
    schon erreicht ist."""
    value = getattr(fact, et.status_field, None)
    if value in et.done or value in et.failed:
        return False                       # Vergangenheit – wird nicht umgeschrieben
    if stage != et.reset:
        return value != stage              # gegenstandslos: nur noch die letzte Stufe zählt
    want = targets.get(fact.article_id)
    return (want is not None and want > ZERO
            and to_qty(getattr(fact, "quantity", 0) or 0) != want)


def rebase_documents(db: Session, order: Order, actor_id: int | None = None) -> list[str]:
    """Die Belege dieses Auftrags auf ihre Grundlage zurücksetzen – **soweit das System das
    allein darf**. Liefert, was sich geändert hat (für Audit/Protokoll). Committet NICHT.

    Ab einer **bindenden** Stufe (``et.binding``) fasst es den Beleg nicht an: dort hat eine
    zweite Partei zugesagt, und das lässt sich nicht einseitig zurücknehmen. Die Abweichung
    bleibt dann als **offene Klärung** stehen (``clarifications``) – sichtbar am Schritt,
    und erst die Bestätigung des Menschen löst dieselbe Änderung aus."""
    from . import process
    targets = target_quantities(db, order)
    changed: list[str] = []
    for step_type, et in STAGED.items():
        stage = _stage_of(order, et)
        if stage is None:
            continue
        for fact in process._facts(db, order, step_type):
            if getattr(fact, et.status_field, None) in et.binding:
                continue                       # Zusage – hier entscheidet der Mensch
            if not _off_basis(order, fact, et, targets, stage):
                continue
            changed.append(f"{step_type}:{getattr(fact, et.status_field)}→{stage}")
            _apply(db, order, fact, et, stage, targets.get(fact.article_id), actor_id)
    return changed


class Clarification(NamedTuple):
    """Eine offene Klärung: der Beleg steht auf einer Menge, die der Auftrag nicht mehr
    braucht – und er ist bindend, also muss ein Mensch mit der Gegenseite reden."""
    article_id: int
    ordered: Decimal      # wofür der Beleg ausgestellt ist
    needed: Decimal       # was der Auftrag noch braucht (0 = gar nichts mehr)


def clarifications(db: Session, order: Order, step_type: str) -> dict[int, Clarification]:
    """**Was an diesem Schritt mit der Gegenseite zu klären ist** – je Artikel, abgeleitet.

    Kein Feld, kein Merker: die Frage ist «Beleg-Menge ≠ Soll, und der Beleg ist bindend».
    Sie beantwortet sich damit von selbst und verschwindet in dem Moment, in dem jemand
    handelt – ein gespeicherter Klärungs-Marker könnte dagegen hängen bleiben."""
    from . import process
    et = STAGED.get(step_type)
    if et is None or not et.binding:
        return {}
    stage = _stage_of(order, et)
    if stage is None:
        return {}
    targets = target_quantities(db, order)
    out: dict[int, Clarification] = {}
    for fact in process._facts(db, order, step_type):
        if getattr(fact, et.status_field, None) not in et.binding:
            continue
        if not _off_basis(order, fact, et, targets, stage):
            continue
        out[fact.article_id] = Clarification(
            article_id=fact.article_id,
            ordered=to_qty(getattr(fact, "quantity", 0) or 0),
            needed=targets.get(fact.article_id, ZERO) if stage == et.reset else ZERO)
    return out


def apply_clarified(db: Session, order: Order, step_type: str, fact,
                    actor_id: int | None) -> str:
    """**Der Mensch hat mit der Gegenseite gesprochen** – jetzt gilt dieselbe Änderung.

    Kein zweiter Weg: derselbe ``_apply`` wie die Automatik, nur ein anderer Auslöser. Der
    Unterschied zwischen «das System darf» und «der Mensch entscheidet» ist damit genau EINE
    Bedingung im Automatik-Pfad – nicht zwei Implementierungen."""
    et = STAGED[step_type]
    stage = _stage_of(order, et)
    targets = target_quantities(db, order)
    if stage is None or not _off_basis(order, fact, et, targets, stage):
        raise HTTPException(409, detail="Hier gibt es nichts zu klären – der Beleg passt zum Auftrag.")
    _apply(db, order, fact, et, stage, targets.get(fact.article_id), actor_id)
    return str(stage)


def _apply(db: Session, order: Order, fact, et: event_types.EventType, stage,
           want: Decimal | None, actor_id: int | None) -> None:
    """Die Stufe setzen, die Vereinbarung räumen, die Menge nachziehen – und es festhalten.

    Die **Menge nachzuziehen ist der eigentliche «Rebase»**: ohne sie stünde der Beleg beim
    nächsten Durchlauf wieder auf einer fremden Grundlage und fiele erneut zurück."""
    old = getattr(fact, et.status_field, None)
    setattr(fact, et.status_field, stage)
    if stage == et.reset:
        for name in et.reset_fields:
            if hasattr(fact, name):
                setattr(fact, name, None)
        if want is not None:
            fact.quantity = want
    table = type(fact).__tablename__
    log_audit(db, table, et.status_field, str(stage), actor_id,
              object_id=order.object_id, old_value=str(old))
    emit(db, f"{et.key}.{'voided' if stage == et.voided else 'rebased'}",
         object_type="order", object_id=order.object_id,
         payload={"article_id": getattr(fact, "article_id", None),
                  "from": old, "to": stage,
                  "quantity": float(want) if want is not None else None},
         actor_id=actor_id)
