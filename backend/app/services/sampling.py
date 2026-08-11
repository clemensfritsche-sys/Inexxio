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

**Je Instanz**, nicht je Auftrag: die Stichprobe wird aus einem Los gezogen, und das Los
ist die Instanz (siehe ``domain/sampling``).
"""

import random
from typing import Any, Iterable, Optional

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from ..domain import modules, sampling as rule_of
from ..models import InstanceUnit, Order, ProcessEvent, ProcessStep
from ..models.process_event import KIND_SAMPLE


def ensure(db: Session, *, order: Order, step: Optional[ProcessStep],
           units: Iterable[InstanceUnit], actor_id: Optional[int]) -> int:
    """Die Stichprobe für ``step`` ziehen, **falls für diese Instanz noch keine gezogen ist**.

    Eine Funktion für beide Anlässe – Ankunft am Modul und (als Netz) das Bestätigen.
    Sie ist **idempotent je (Modul, Instanz)**: gibt es dort schon eine Ziehung, passiert
    nichts. Damit gilt «einmal und eingefroren», ohne dass zwei Aufrufstellen sich
    absprechen müssen; und der Grenzfall «das gezogene Stück wurde von einer Abweichung
    geholt» fällt heraus, statt eine eigene Regel zu brauchen.

    Kein Modul, keine Ziehung: hinter dem Ende gibt es nichts mehr zu erfassen. Ist die
    Regel «alle», wird trotzdem gezogen – dann ist jede Zeile eine gezogene, und die
    Historie sagt dasselbe wie bei jeder anderen Regel. Ein Sonderfall «alle braucht keine
    Einträge» hiesse, dass jede Ansicht zwei Fälle unterscheiden muss.

    Gibt die Zahl der neu gezogenen Stücke zurück.
    """
    units = list(units)
    if step is None or not units:
        return 0
    rule = modules.sample_of(step.config)

    by_instance: dict[int, list[InstanceUnit]] = {}
    for u in units:
        by_instance.setdefault(u.instance_id, []).append(u)
    already = _instances_drawn(db, order=order, step=step, instance_ids=list(by_instance))

    rows: list[dict[str, Any]] = []
    for instance_id, group in by_instance.items():
        if instance_id in already:
            continue
        # Stabile Ausgangsordnung, dann Zufall: ohne die Sortierung hinge das Ergebnis an
        # der Reihenfolge, in der die Datenbank die Zeilen liefert – und die ist keine
        # Zufallsquelle, sondern eine unbekannte.
        group.sort(key=lambda u: u.id)
        picked = random.sample(group, rule_of.size(rule, len(group)))
        for u in sorted(picked, key=lambda u: u.id):
            rows.append({
                "order_id": order.id,
                "step_id": step.id,
                "instance_unit_id": u.id,
                "kind": KIND_SAMPLE,
                # Gezogen zu werden ist keine Zustandsänderung des Stücks.
                "status_before": u.status,
                "status_after": u.status,
                "payload": {"rule": rule, "of": len(group)},
                "actor_id": actor_id,
            })
    if rows:
        db.execute(insert(ProcessEvent), rows)
    return len(rows)


def _instances_drawn(db: Session, *, order: Order, step: ProcessStep,
                     instance_ids: list[int]) -> set[int]:
    """Für welche dieser Instanzen ist an diesem Modul **schon** gezogen worden?"""
    if not instance_ids:
        return set()
    return {
        int(iid)
        for (iid,) in db.execute(
            select(InstanceUnit.instance_id)
            .join(ProcessEvent, ProcessEvent.instance_unit_id == InstanceUnit.id)
            .where(
                ProcessEvent.order_id == order.id,
                ProcessEvent.step_id == step.id,
                ProcessEvent.kind == KIND_SAMPLE,
                InstanceUnit.instance_id.in_(instance_ids),
            )
            .distinct()
        ).all()
    }


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
