"""**Die Ziehung der Stichprobe — einmal, zufällig, eingefroren.**

Die *Regel* steht in der Definition (``domain/sampling``); hier wird sie angewandt.
Drei Entscheidungen, und jede hat einen Grund:

**Wann?** In dem Moment, in dem die Stücke am Modul **ankommen**. Vorher steht die Menge
nicht fest – ein Abweichungsauftrag kann bis dahin Stücke herausgenommen haben. Nachher
wäre die Ziehung beeinflussbar: wer sie erst beim Erfassen auslöst, kann sie durch die
Reihenfolge seiner Klicks lenken.

**Wie?** **Zufällig.** Eine deterministische Regel («jedes zehnte Stück») ist
vorhersehbar, und Vorhersehbares wird in der Fertigung unterlaufen – ISO 2859-1 verlangt
deshalb ausdrücklich eine Zufallsauswahl. Der Einwand «deterministisch wäre
nachvollziehbarer» trifft nicht: die Nachvollziehbarkeit kommt nicht vom Algorithmus,
sondern vom **festgehaltenen Ergebnis**, und das steht ohnehin im Log. Ein Seed brächte
Reproduzierbarkeit, die niemand braucht, wenn die Auswahl schwarz auf weiss dasteht.

**Wo?** Im Ereignis-Log (``KIND_SAMPLE``), eine Zeile je gezogenem Stück. Der Log ist
append-only – damit ist «eingefroren» keine Zusage, sondern eine Eigenschaft. Ein Feld am
Modul wäre der zweite Ort, an dem dieselbe Aussage steht, und der änderbare dazu.

**Über die Gesamtmenge**, nicht je Instanz: das Modul steht im Prozess und sieht, was
davorsteht – die Summe aller Einzelinstanzen dieses Auftrags (siehe ``domain/sampling``).

**Woraus genau?** Aus allen Stücken, die der Auftrag zu diesem Zeitpunkt noch hält –
nicht nur aus denen, die gerade eben am Modul angekommen sind. Die Stücke erreichen ein
Modul in Wellen (ein Vorgang ist eine Instanz, §4.4); zöge man je Welle, wäre «25 %» in
Wirklichkeit «25 % aus jeder Kiste», also genau die Regel je Instanz, die hier abgeschafft
ist. Gezogen wird darum **einmal je Modul**, in dem Moment, in dem es erreicht wird, über
den vollen Bestand des Auftrags.
"""

import random
from typing import Any, Iterable, Optional

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..domain import modules, sampling as rule_of
from ..models import InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep
from ..models.process_event import KIND_SAMPLE


def ensure(db: Session, *, order: Order, step: Optional[ProcessStep],
           actor_id: Optional[int]) -> int:
    """Die Stichprobe für ``step`` ziehen, **falls dort noch keine gezogen ist**.

    Eine Funktion für beide Anlässe – Erreichen des Moduls und (als Netz) das Bestätigen.
    Sie ist **idempotent je Modul**: gibt es dort schon eine Ziehung, passiert nichts.
    Damit gilt «einmal und eingefroren», ohne dass zwei Aufrufstellen sich absprechen
    müssen.

    Kein Modul, keine Ziehung: hinter dem Ende gibt es nichts mehr zu erfassen. Ist die
    Regel «alle», wird trotzdem gezogen – dann ist jede Zeile eine gezogene, und die
    Historie sagt dasselbe wie bei jeder anderen Regel. Ein Sonderfall «alle braucht keine
    Einträge» hiesse, dass jede Ansicht zwei Fälle unterscheiden muss.

    Gibt die Zahl der gezogenen Stücke zurück.
    """
    if step is None or _drawn_already(db, order=order, step=step):
        return 0
    units = _population(db, order)
    if not units:
        return 0
    rule = modules.sample_of(step.config)
    # Stabile Ausgangsordnung, dann Zufall: ohne die Sortierung hinge das Ergebnis an der
    # Reihenfolge, in der die Datenbank die Zeilen liefert – und die ist keine
    # Zufallsquelle, sondern eine unbekannte.
    units.sort(key=lambda u: u.id)
    picked = random.sample(units, rule_of.size(rule, len(units)))
    rows: list[dict[str, Any]] = [
        {
            "order_id": order.id,
            "step_id": step.id,
            "instance_unit_id": u.id,
            "kind": KIND_SAMPLE,
            # Gezogen zu werden ist keine Zustandsänderung des Stücks.
            "status_before": u.status,
            "status_after": u.status,
            "payload": {"rule": rule, "of": len(units)},
            "actor_id": actor_id,
        }
        for u in sorted(picked, key=lambda u: u.id)
    ]
    db.execute(insert(ProcessEvent), rows)
    return len(rows)


def _population(db: Session, order: Order) -> list[InstanceUnit]:
    """Woraus gezogen wird: **alles, was dieser Auftrag noch hält**.

    Nicht «was gerade vor dem Modul steht»: an einem späteren Modul wäre das die erste
    Welle, und die Bezugsgrösse hinge daran, wie viele Instanzen zufällig schon durch
    sind. Ein ausgeschertes oder angekommenes Stück zählt nicht mit – es kommt hier nie
    (mehr) vorbei.
    """
    return [
        u
        for (u,) in db.execute(
            select(InstanceUnit)
            .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
            .where(
                OrderUnit.order_id == order.id,
                OrderUnit.released_at.is_(None),
                InstanceUnit.is_active.is_(True),
            )
        ).all()
    ]


def _drawn_already(db: Session, *, order: Order, step: ProcessStep) -> bool:
    """Ist an diesem Modul **schon** gezogen worden?"""
    return db.execute(
        select(ProcessEvent.id).where(
            ProcessEvent.order_id == order.id,
            ProcessEvent.step_id == step.id,
            ProcessEvent.kind == KIND_SAMPLE,
        ).limit(1)
    ).first() is not None


def drawn_at(db: Session, *, order: Order, step: ProcessStep,
             unit_ids: Iterable[int]) -> set[int]:
    """Welche dieser Stücke sind an diesem Modul **gezogen**? — aus dem Log gelesen.

    Nicht neu gerechnet: die Ziehung ist einmalig, und sie ein zweites Mal zu würfeln
    ergäbe eine andere Antwort. Genau darum steht sie im Log.
    """
    unit_ids = list(unit_ids)
    if not unit_ids:
        return set()
    return {
        int(uid)
        for (uid,) in db.execute(
            select(ProcessEvent.instance_unit_id).where(
                ProcessEvent.order_id == order.id,
                ProcessEvent.step_id == step.id,
                ProcessEvent.kind == KIND_SAMPLE,
                ProcessEvent.instance_unit_id.in_(unit_ids),
            ).distinct()
        ).all()
    }
