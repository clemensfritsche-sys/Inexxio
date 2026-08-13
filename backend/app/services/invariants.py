"""**Die Invarianten — über den GESAMTEN Bestand, nicht über ein Szenario.**

Ein Szenariotest prüft, was jemand sich ausgedacht hat. Eine Invariante prüft, was
**wahr sein muss** — auch in den Fällen, an die niemand gedacht hat. Sie ist damit das
Netz unter allem, was hier noch gebaut wird.

Jede Prüfung ist ein Satz aus ``SYSTEM_LOGIC.md`` und gibt die **Verstösse** zurück, nicht
True/False: eine Verletzung ohne Nennung des betroffenen Datensatzes ist eine Meldung, mit
der niemand etwas anfangen kann.

**Sie sind absichtlich unabhängig von der Fachlogik formuliert.** Wo möglich wird gegen
die *Tabellen* geprüft, nicht gegen die Ableitung, die geprüft werden soll — sonst
bestätigte die Ableitung sich selbst. Die zwei Ausnahmen sind benannt (``I05``, ``I07``):
dort ist die Ableitung der Gegenstand, und geprüft wird ihr **Widerspruch** zu den Daten.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import (
    Instance, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent, ProcessStep,
)
from ..models.process_event import KIND_START
from . import process

#: Wie viele Verstösse eine Prüfung höchstens aufzählt. Ein Deckel, der **ausgewiesen**
#: wird – eine Liste, die stumm bei 20 aufhört, sieht aus wie die ganze Wahrheit.
LIMIT = 20


@dataclass
class Check:
    key: str
    title: str
    rule: str
    fn: Callable[[Session], list[str]]


@dataclass
class Finding:
    check: Check
    violations: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.violations


CHECKS: list[Check] = []


def _check(key: str, title: str, rule: str):
    def deco(fn):
        CHECKS.append(Check(key=key, title=title, rule=rule, fn=fn))
        return fn
    return deco


# ---------------------------------------------------------------------------
# G2 · Exklusivität
# ---------------------------------------------------------------------------

@_check("I01", "Jede Einzelinstanz ist in höchstens EINEM Auftrag aktiv",
        "G2 – aktiv heisst offene Zugehörigkeit; zwei davon darf es nie geben.")
def i01(db: Session) -> list[str]:
    rows = db.execute(
        select(OrderUnit.instance_unit_id, func.count(OrderUnit.id))
        .where(OrderUnit.released_at.is_(None))
        .group_by(OrderUnit.instance_unit_id)
        .having(func.count(OrderUnit.id) > 1)
        .limit(LIMIT + 1)
    ).all()
    return [f"Einzelinstanz #{uid} hat {n} offene Zugehörigkeiten" for uid, n in rows]


@_check("I02", "Eine offene Zugehörigkeit steht IMMER vor einem Modul",
        "§4.1 – wer das Ende passiert, wird frei; die Zeile wird dabei geschlossen.")
def i02(db: Session) -> list[str]:
    rows = db.execute(
        select(OrderUnit.id, OrderUnit.order_id)
        .where(OrderUnit.released_at.is_(None), OrderUnit.current_step_id.is_(None))
        .limit(LIMIT + 1)
    ).all()
    return [f"Zeile #{i} (Auftrag #{o}) ist offen, steht aber vor keinem Modul"
            for i, o in rows]


@_check("I03", "Der Zustandspunkt gehört zum eigenen Auftrag",
        "G1 – «wo steht dieses Stück» ist eine Aussage über DIESE Zugehörigkeit.")
def i03(db: Session) -> list[str]:
    rows = db.execute(
        select(OrderUnit.id, OrderUnit.order_id, OrderUnit.current_step_id)
        .join(ProcessStep, ProcessStep.id == OrderUnit.current_step_id, isouter=True)
        .where(
            OrderUnit.current_step_id.isnot(None),
            (ProcessStep.id.is_(None)) | (ProcessStep.order_id != OrderUnit.order_id),
        )
        .limit(LIMIT + 1)
    ).all()
    return [f"Zeile #{i} (Auftrag #{o}) zeigt auf Modul #{s} eines anderen Auftrags"
            for i, o, s in rows]


# ---------------------------------------------------------------------------
# G4/G5 · Terminale Status und der eingefrorene Log
# ---------------------------------------------------------------------------

@_check("I04", "Kein Statuswechsel führt aus einem terminalen Status heraus",
        "G4 – geprüft am LOG, nicht an der Absicht: ein Eintrag, dessen Vorher-Zustand "
        "terminal ist, wäre der Beweis.")
def i04(db: Session) -> list[str]:
    if not st.TERMINAL_UNIT_STATUSES:
        return []
    rows = db.execute(
        select(ProcessEvent.id, ProcessEvent.instance_unit_id,
               ProcessEvent.status_before, ProcessEvent.status_after)
        .where(ProcessEvent.status_before.in_(list(st.TERMINAL_UNIT_STATUSES)),
               ProcessEvent.status_before != ProcessEvent.status_after)
        .limit(LIMIT + 1)
    ).all()
    return [f"Ereignis #{i}: Einzelinstanz #{u} ging von «{b}» nach «{a}»"
            for i, u, b, a in rows]


@_check("I05", "Log und Zeile widersprechen sich nicht",
        "G5 – der Log sagt Endzustand, die Zeile sagt etwas anderes: dann hat jemand "
        "AUSSERHALB der Prozesslogik geschrieben (Migration 110).")
def i05(db: Session) -> list[str]:
    rows = db.execute(text(f"""
        SELECT u.id, u.status, e.status_after
        FROM instance_units u
        JOIN LATERAL (
            SELECT status_after FROM process_events
            WHERE instance_unit_id = u.id ORDER BY id DESC LIMIT 1
        ) e ON TRUE
        WHERE e.status_after = ANY(:terminal) AND u.status <> e.status_after
        LIMIT {LIMIT + 1}
    """), {"terminal": list(st.TERMINAL_UNIT_STATUSES)}).all()
    return [f"Einzelinstanz #{i}: Log «{log}», Zeile «{row}»" for i, row, log in rows]


@_check("I06", "Jeder gespeicherte Zustand steht im Katalog",
        "§1.1 – die Liste ist geschlossen; ein Wert daneben ist im System nicht gültig.")
def i06(db: Session) -> list[str]:
    out: list[str] = []
    rows = db.execute(
        select(InstanceUnit.status, func.count(InstanceUnit.id))
        .where(InstanceUnit.status.notin_(list(st.UNIT_STATUSES)))
        .group_by(InstanceUnit.status).limit(LIMIT + 1)
    ).all()
    out += [f"{n} Einzelinstanzen tragen «{s}» – kein Stück-Zustand" for s, n in rows]
    rows = db.execute(
        select(ProcessEvent.status_after, func.count(ProcessEvent.id))
        .where(ProcessEvent.status_after.notin_(list(st.UNIT_STATUSES)))
        .group_by(ProcessEvent.status_after).limit(LIMIT + 1)
    ).all()
    out += [f"{n} Log-Einträge enden auf «{s}» – kein Stück-Zustand" for s, n in rows]
    return out


# ---------------------------------------------------------------------------
# §2 · Auftragsstatus
# ---------------------------------------------------------------------------

@_check("I07", "Der Auftragsstatus passt zum Zustand seiner Stücke",
        "§2.1 – abgeleitet heisst: er darf der Zeilenlage nie widersprechen.")
def i07(db: Session) -> list[str]:
    from . import process as proc

    ids = [int(i) for (i,) in db.execute(select(Order.id)).all()]
    if not ids:
        return []
    derived = proc.order_statuses(db, ids)
    # **Dieselbe Grundgesamtheit wie die Ableitung.** Sonst vergliche diese Invariante
    # zwei verschiedene Mengen und meldete genau den Unterschied als Fehler – Material
    # gehört dem Auftrag, ist aber nicht sein Gegenstand (§9.6a), und ``order_statuses``
    # zählt es darum nicht mit.
    lage = {
        int(oid): (int(offen), int(gesamt))
        for oid, offen, gesamt in db.execute(
            select(
                OrderUnit.order_id,
                func.count(OrderUnit.id).filter(OrderUnit.released_at.is_(None)),
                func.count(OrderUnit.id),
            ).where(process.material_clause()).group_by(OrderUnit.order_id)
        ).all()
    }
    out: list[str] = []
    for oid in ids:
        offen, gesamt = lage.get(oid, (0, 0))
        status = derived.get(oid)
        if gesamt == 0:
            out.append(f"Auftrag #{oid} hat gar keine Einzelinstanz")
        elif offen > 0 and status != st.IM_PROZESS:
            out.append(f"Auftrag #{oid}: {offen} Stück offen, Status «{status}»")
        elif offen == 0 and status == st.IM_PROZESS:
            # Zulässig **nur**, wenn etwas verliehen ist und zurückkommt.
            if not proc.waiting_counts(db, [oid]).get(oid):
                out.append(f"Auftrag #{oid}: nichts offen, nichts verliehen, "
                           f"trotzdem «{st.IM_PROZESS}»")
        if len(out) > LIMIT:
            break
    return out


@_check("I08", "Die Menge stimmt: Definitionszeilen == Einzelinstanzen",
        "G3 – Menge N heisst, danach laufen exakt N Stück. Die Zeilen bleiben stehen, "
        "auch wenn sich ihr Zustand ändert.")
def i08(db: Session) -> list[str]:
    soll = {
        int(oid): int(n or 0)
        for oid, n in db.execute(
            select(OrderLine.order_id, func.sum(OrderLine.quantity))
            .group_by(OrderLine.order_id)
        ).all()
    }
    # **Gezählt werden Subjekte.** Der Bedarf sagt, was ein Auftrag *bearbeitet*;
    # **Material** steht nicht darin – es kommt aus der Stückliste eines Moduls und
    # tritt dort ein (§9.6a). Zählte es mit, meldete jeder Auftrag mit einer Vormerkung
    # eine Abweichung, die keine ist – und ein Wächter, der im Normalbetrieb anschlägt,
    # ist von einem kaputten nicht zu unterscheiden.
    ist = {
        int(oid): int(n)
        for oid, n in db.execute(
            select(OrderUnit.order_id, func.count(OrderUnit.id))
            .where(process.material_clause())
            .group_by(OrderUnit.order_id)
        ).all()
    }
    out = []
    for oid in sorted(set(soll) | set(ist)):
        if soll.get(oid, 0) != ist.get(oid, 0):
            out.append(f"Auftrag #{oid}: Definition {soll.get(oid, 0)}, "
                       f"Zeilen {ist.get(oid, 0)}")
    return out[: LIMIT + 1]


# ---------------------------------------------------------------------------
# §12 · Rückführung
# ---------------------------------------------------------------------------

@_check("I09", "Jede wartende Rückführung hat einen Gegenpart",
        "§12.4 – die Rückkehrposition ist die geschlossene Zeile des Quell-Auftrags "
        "mit gesetztem Zustandspunkt. Zeigt sie ins Leere, kommt das Stück nirgends an.")
def i09(db: Session) -> list[str]:
    loans = db.execute(
        select(OrderUnit.id, OrderUnit.instance_unit_id, OrderUnit.return_to_order_id)
        .where(OrderUnit.released_at.is_(None), OrderUnit.return_to_order_id.isnot(None))
    ).all()
    if not loans:
        return []
    homes = {
        (int(o), int(u))
        for o, u in db.execute(
            select(OrderUnit.order_id, OrderUnit.instance_unit_id)
            .where(OrderUnit.released_at.isnot(None),
                   OrderUnit.current_step_id.isnot(None))
        ).all()
    }
    return [
        f"Zeile #{i}: Einzelinstanz #{u} soll nach Auftrag #{o} zurück, "
        f"findet dort aber keine offene Stelle"
        for i, u, o in loans if (int(o), int(u)) not in homes
    ][: LIMIT + 1]


@_check("I10", "Eine Rückführung zeigt auf einen Auftrag, den es gibt",
        "G3 – ein Verweis ins Leere ist ein Loch in Bestand und Historie.")
def i10(db: Session) -> list[str]:
    rows = db.execute(
        select(OrderUnit.id, OrderUnit.return_to_order_id)
        .join(Order, Order.id == OrderUnit.return_to_order_id, isouter=True)
        .where(OrderUnit.return_to_order_id.isnot(None), Order.id.is_(None))
        .limit(LIMIT + 1)
    ).all()
    return [f"Zeile #{i} führt nach Auftrag #{o} zurück – den gibt es nicht"
            for i, o in rows]


# ---------------------------------------------------------------------------
# Nummern und Identität
# ---------------------------------------------------------------------------

@_check("I11", "Jede Objektnummer existiert genau einmal",
        "§0 – ein universeller Nummernkreis über alle Objekttypen.")
def i11(db: Session) -> list[str]:
    rows = db.execute(text(f"""
        SELECT object_id, count(*) FROM (
            SELECT object_id FROM orders
            UNION ALL SELECT object_id FROM instances
            UNION ALL SELECT object_id FROM articles WHERE object_id IS NOT NULL
        ) alle GROUP BY object_id HAVING count(*) > 1 LIMIT {LIMIT + 1}
    """)).all()
    return [f"Objektnummer {o} kommt {n}-mal vor" for o, n in rows]


@_check("I12", "Jede Einzelinstanz gehört zu einer Instanz, die es gibt",
        "G1 – ihre Nummer ist von der Instanz abgeleitet; ohne sie hat sie keine.")
def i12(db: Session) -> list[str]:
    rows = db.execute(
        select(InstanceUnit.id, InstanceUnit.instance_id)
        .join(Instance, Instance.id == InstanceUnit.instance_id, isouter=True)
        .where(Instance.id.is_(None))
        .limit(LIMIT + 1)
    ).all()
    return [f"Einzelinstanz #{i} verweist auf Instanz #{n}, die es nicht gibt"
            for i, n in rows]


@_check("I13", "Jedes Stück im Prozess hat einen Auftrag, der es hält",
        "G2 – «Im Prozess» heisst: in genau einem Auftrag. Ohne Zeile wäre der Zustand "
        "eine Behauptung.")
def i13(db: Session) -> list[str]:
    rows = db.execute(text(f"""
        SELECT u.id FROM instance_units u
        WHERE u.status = :laufend
          AND NOT EXISTS (
            SELECT 1 FROM order_units m
            WHERE m.instance_unit_id = u.id AND m.released_at IS NULL
          )
        LIMIT {LIMIT + 1}
    """), {"laufend": st.IM_PROZESS}).all()
    return [f"Einzelinstanz #{i} steht auf «Im Prozess», wird aber von keinem Auftrag "
            f"gehalten" for (i,) in rows]


@_check("I14", "Jeder Auftrag hat genau ein Start-Ereignis je Stück",
        "§6.3 – das Start-Objekt wird einmal passiert; zweimal hiesse, das Stück wäre "
        "zweimal eingetreten.")
def i14(db: Session) -> list[str]:
    rows = db.execute(
        select(ProcessEvent.order_id, ProcessEvent.instance_unit_id,
               func.count(ProcessEvent.id))
        .where(ProcessEvent.kind == KIND_START)
        .group_by(ProcessEvent.order_id, ProcessEvent.instance_unit_id)
        .having(func.count(ProcessEvent.id) > 1)
        .limit(LIMIT + 1)
    ).all()
    return [f"Auftrag #{o}: Einzelinstanz #{u} hat {n} Start-Einträge"
            for o, u, n in rows]


# ---------------------------------------------------------------------------
# Das Bild
# ---------------------------------------------------------------------------

@_check("I15", "Das Prozessbild ist für jeden Auftrag widerspruchsfrei",
        "§8.1a – jede Einzelinstanz steht auf genau einer Kante, und eine Kante mit "
        "Stücken gilt als gegangen. Die Prüfung steckt im Graph selbst.")
def i15(db: Session) -> list[str]:
    from . import flow as flow_svc

    out: list[str] = []
    for (oid,) in db.execute(select(Order.id).order_by(Order.id)).all():
        order = db.get(Order, int(oid))
        if order is None:
            continue
        try:
            problems = flow_svc.build(db, order).problems
        except Exception as exc:                               # noqa: BLE001
            out.append(f"Auftrag {order.object_id}: Bild nicht baubar "
                       f"({type(exc).__name__}: {exc})")
            continue
        out += [f"Auftrag {order.object_id}: {p}" for p in problems]
        if len(out) > LIMIT:
            break
    return out


# ---------------------------------------------------------------------------
# Aufruf
# ---------------------------------------------------------------------------

def size_of(db: Session) -> str:
    """Wie gross ist der geprüfte Bestand? Eine Invariantenprüfung über nichts ist keine."""
    counts = {
        "Aufträge": db.execute(select(func.count(Order.id))).scalar() or 0,
        "Instanzen": db.execute(select(func.count(Instance.id))).scalar() or 0,
        "Einzelinstanzen": db.execute(select(func.count(InstanceUnit.id))).scalar() or 0,
        "Zugehörigkeiten": db.execute(select(func.count(OrderUnit.id))).scalar() or 0,
        "Log-Einträge": db.execute(select(func.count(ProcessEvent.id))).scalar() or 0,
    }
    return " · ".join(f"{v} {k}" for k, v in counts.items())


def run(db: Session, *, only: Optional[set[str]] = None) -> list[Finding]:
    """Alle Invarianten fahren. **Rein lesend** – sie prüfen, sie reparieren nie."""
    out: list[Finding] = []
    for check in CHECKS:
        if only and check.key not in only:
            continue
        found = check.fn(db)
        out.append(Finding(check=check, violations=found[:LIMIT],
                           truncated=len(found) > LIMIT))
    return out
