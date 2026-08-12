"""**Der Prozess: Freigabe, Schritt bestätigen, Zustand ableiten.**

Die eine Stelle, an der Einzelinstanzen ihren Status wechseln. Jeder Wechsel schreibt
im selben Atemzug einen Eintrag in den Ereignis-Log (Ebene 3) und zieht die Projektionen
nach (Ebene 2) — es gibt keinen zweiten Schreibweg, und darum können die beiden nicht
auseinanderlaufen.

Gelesen wird PROCESS_CORE.md; hier steht nur, was daraus folgt.
"""

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, insert, update
from sqlalchemy.orm import Session

from ..domain import chain, modules, statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent,
    ProcessStep,
)
from ..models.order_line import LAGER, NEU, ORIGINS
from ..models.process_event import (
    KIND_CAPTURE, KIND_END, KIND_HANDOVER, KIND_RETURN, KIND_SAMPLE, KIND_START, KIND_STEP,
)
from . import article_process, capture as capture_svc, materialize, sampling
from .instances import unit_number

#: Wie die Instanz vor der Eingabe verifiziert wurde. **Beides ist eine Bestätigung** –
#: die Tastatur ist die Alternative zum Scan, nicht seine Umgehung, und beides steht im
#: Log. Ohne den Vermerk wäre «getippt» von «gescannt» hinterher nicht zu unterscheiden,
#: und die Scan-Pflicht wäre eine Behauptung.
VERIFY_SCAN, VERIFY_MANUAL = "scan", "manual"
VERIFICATIONS = (VERIFY_SCAN, VERIFY_MANUAL)

#: Wie viele Werte höchstens in eine ``IN``-Liste kommen. Bei 5000 Stück wäre eine
#: einzige Liste ein Abfrage-Text von hunderten Kilobyte; das ist kein Fehler, aber
#: unnötig – und die Grenze kostet nichts.
_CHUNK = 1000


def _chunks(values: list[int]) -> Iterable[list[int]]:
    for i in range(0, len(values), _CHUNK):
        yield values[i:i + _CHUNK]


# ---------------------------------------------------------------------------
# Der Ereignis-Log — die EINE Schreibstelle für einen Statuswechsel
# ---------------------------------------------------------------------------

def _pass(
    db: Session,
    *,
    order: Order,
    units: list[InstanceUnit],
    membership_ids: list[int],
    kind: str,
    step: Optional[ProcessStep],
    status_after: str,
    next_step_id: Optional[int],
    actor_id: Optional[int],
    payloads: Optional[dict[int, dict[str, Any]]] = None,
) -> int:
    """Stücke passieren ein Prozessobjekt.

    Log **und** Projektionen in einem Aufruf. Getrennt wären es zwei Schreibwege, und
    der Wächter «Projektion == Replay(Log)» wäre eine Hoffnung statt einer Folge.

    Die Funktion arbeitet auf einer **Liste**, nicht auf einem Stück: bei 5000 Stück
    wären 15 000 einzelne Anweisungen der Grund, warum «flüssig» nicht mehr stimmt. Ein
    zweiter, schneller Pfad daneben wäre genau der zweite Schreibweg, den es nicht geben
    darf – also ist die Menge hier der Normalfall und das einzelne Stück ihr Sonderfall.
    """
    if not units:
        return 0

    # Der Vorher-Status wird gelesen, **bevor** geschrieben wird – sonst stünde im Log
    # zweimal derselbe Wert und der Übergang wäre nicht mehr ablesbar.
    db.execute(
        insert(ProcessEvent),
        [
            {
                "order_id": order.id,
                "step_id": step.id if step else None,
                "instance_unit_id": u.id,
                "kind": kind,
                "status_before": u.status,
                "status_after": status_after,
                # Was das Modul dabei festgehalten hat – bei der Datenerfassung die
                # ``captures``-Zeile dieses Stücks. Der Log verweist darauf, statt die
                # Werte ein zweites Mal zu führen: zwei Kopien laufen auseinander.
                "payload": (payloads or {}).get(u.id),
                "actor_id": actor_id,
            }
            for u in units
        ],
    )

    unit_ids = [u.id for u in units]
    for part in _chunks(unit_ids):
        db.execute(
            update(InstanceUnit)
            .where(InstanceUnit.id.in_(part))
            .values(status=status_after)
            .execution_options(synchronize_session=False)
        )
    # Am Ende angekommen: das Stück verlässt den Auftrag und ist wieder frei. Genau hier
    # fällt die Exklusivität weg – der partielle Unique-Index greift ab jetzt nicht mehr.
    released = None if next_step_id is not None else datetime.now(timezone.utc)
    for part in _chunks(membership_ids):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(current_step_id=next_step_id, released_at=released)
            .execution_options(synchronize_session=False)
        )
    for u in units:
        u.status = status_after
    return len(units)


# ---------------------------------------------------------------------------
# Die Definitionszeilen
# ---------------------------------------------------------------------------

class _Line:
    """Eine aufgelöste Definitionszeile – Artikel statt Objektnummer, geprüft."""

    def __init__(self, position: int, article: Article, quantity: int, origin: str,
                 picks: list[tuple[str, Optional[int]]], returns: bool = True):
        self.position = position
        self.article = article
        self.quantity = quantity
        self.origin = origin
        #: Je gewähltem Stück seine Nummer **und der Auftrag, in dem es bei der Auswahl
        #: lief** (``None`` = frei). Die zweite Hälfte ist die Absicht des Menschen und
        #: wird bei der Freigabe gegen die Wirklichkeit geprüft (``_assert_as_picked``).
        self.picks = picks
        #: Kehren übernommene Stücke in ihren Quell-Auftrag zurück? Nur für Stücke
        #: bedeutsam, die aus einem laufenden Auftrag kommen – ein freies Stück hat
        #: keinen Auftrag, in den es zurückkönnte.
        self.returns = returns
        self.units: list[InstanceUnit] = []
        #: Je übernommenem Stück die **offene Zeile des Quell-Auftrags**. Sie ist die
        #: Verbindung: sie trägt die Rückkehrposition und wird bei der Rückführung
        #: wieder geöffnet.
        self.taken: dict[int, OrderUnit] = {}

    @property
    def label(self) -> str:
        return f"Zeile {self.position} ({self.article.name})"


def resolve_lines(db: Session, raw: list[dict[str, Any]]) -> list[_Line]:
    """Rohe Definitionszeilen prüfen und auflösen. Jeder Verstoss ist ein harter Fehler."""
    out: list[_Line] = []
    for position, row in enumerate(raw, start=1):
        origin = row.get("origin")
        if origin not in ORIGINS:
            raise HTTPException(
                status_code=400,
                detail=f"Zeile {position}: «{origin}» ist keine Herkunft. Erlaubt: {', '.join(ORIGINS)}.",
            )
        object_id = row.get("article_object_id")
        article = (
            db.query(Article).filter(Article.object_id == object_id).first()
            if object_id else None
        )
        if article is None or not article.is_active:
            raise HTTPException(
                status_code=404, detail=f"Zeile {position}: Artikel {object_id} gibt es nicht.",
            )
        quantity = int(row.get("quantity") or 0)
        if quantity < 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Zeile {position} ({article.name}): die Menge muss mindestens 1 sein. "
                    f"Eine Zeile ohne Stück bewegt nichts."
                ),
            )
        out.append(_Line(
            position=position,
            article=article,
            quantity=quantity,
            origin=origin,
            picks=[
                (str(u.get("number") or "").strip(), u.get("from_order"))
                for u in (row.get("units") or [])
            ],
            returns=bool(row.get("returns", True)),
        ))
    _assert_single_new(out)
    return out


def _assert_single_new(lines: list[_Line]) -> None:
    """**«Neu» ist eine Herkunft für sich allein** (Testnotiz #693).

    Ein Erzeugungsauftrag fährt die **Vorlage des Artikels**, als Kopie mit
    Versionsstempel (§2.1). Der Stempel sagt «diese Stücke sind genau so entstanden, wie
    Artikel X es beschreibt» – und das gilt nur für die Stücke dieses einen Artikels. Eine
    zweite Zeile liefe durch denselben Prozess, obwohl er nicht ihrer ist: der Stempel
    wäre für sie eine Behauptung.

    Die Regel liest sich von beiden Enden gleich: mit «Neu» kommt keine zweite Zeile dazu,
    und zu einer zweiten Zeile lässt sich «Neu» nicht mehr wählen. Zwei Erzeugungen sind
    zwei Aufträge.
    """
    new_lines = [ln for ln in lines if ln.origin == NEU]
    if new_lines and len(lines) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{new_lines[0].label}: «Neu» steht für sich allein – ein Erzeugungsauftrag "
                f"fährt die Vorlage genau dieses Artikels. Für den zweiten Artikel einen "
                f"eigenen Auftrag anlegen."
            ),
        )


def _from_module(data: dict[str, Any]) -> dict[str, Any]:
    """Eine Modul-Definition aus dem Entwurf in ihre gespeicherte Form bringen.

    **Der Übergang wird abgeleitet, nicht übernommen**: er gehört zum Modultyp
    (``domain/modules``). Was der Entwurf schickt, ist Typ und Konfiguration – und die
    läuft durch die Prüfung des Moduls, nicht durch eine Kopie davon.
    """
    module = modules.get(data.get("module_type"))
    config = module.clean_config(data.get("config"))
    return {
        "module_type": module.key,
        "status_before": module.status_before,
        # **Erst prüfen, dann ableiten.** Beim Aussondern hängt das Nachher an der
        # Ausprägung – gefragt wird also die bereinigte Konfiguration, nie die rohe.
        "status_after": module.status_after_for(config),
        "config": config,
    }


def steps_for(db: Session, lines: list[_Line], submitted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Welcher Prozess gilt für diesen Auftrag?

    - Enthält er eine ``Neu``-Zeile, ist es die **Vorlage des Artikels**, als Kopie mit
      Versionsstempel. Sie ist nicht verhandelbar: neue Stücke entstehen genau so, wie
      der Artikel es sagt, sonst wäre der Stempel eine Behauptung.
    - Sonst (reiner ``Lager``-Auftrag) ist es der im Entwurf modellierte Prozess.

    Eine ``Neu``-Zeile steht für sich allein (``_assert_single_new``, #693) – die Frage
    «welche von zwei Vorlagen gilt» kann es darum gar nicht geben.
    """
    new_lines = [ln for ln in lines if ln.origin == NEU]
    if not new_lines:
        return [_from_module(s) for s in submitted]

    ln = new_lines[0]
    copied = article_process.mirror(db, ln.article)
    if not copied:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{ln.label}: dieser Artikel hat keinen Erzeugungsprozess. "
                f"«Neu» ist erst wählbar, wenn im Artikel-Reiter «Erzeugungsprozess» "
                f"mindestens ein Modul steht."
            ),
        )
    return copied


# ---------------------------------------------------------------------------
# Freigabe
# ---------------------------------------------------------------------------

def assert_releasable(total_units: int, steps: list[dict[str, Any]]) -> list[str]:
    """Die beiden harten Freigabebedingungen (§6.2) — als Liste dessen, was **fehlt**.

    Namen statt True/False, damit die Oberfläche sagen kann *was* fehlt, statt den
    Nutzer suchen zu lassen. Dieselbe Funktion beantwortet ``/validate`` und schützt
    die Anlage: eine deaktivierte Schaltfläche ist keine Absicherung, sondern eine Bitte.
    """
    missing: list[str] = []
    if total_units < 1:
        missing.append("mindestens eine Einzelinstanz")
    if not steps:
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def _resolve_units(db: Session, numbers: list[str], *, seen: set[str]) -> list[tuple[InstanceUnit, str]]:
    """Nummern → Einzelinstanzen. Unbekannt oder doppelt = harter Fehler, kein Filtern."""
    from .instances import find_unit

    out: list[tuple[InstanceUnit, str]] = []
    for raw in numbers:
        number = (raw or "").strip()
        if number in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Einzelinstanz {number} ist doppelt in der Definition.",
            )
        seen.add(number)
        unit = find_unit(db, number)
        if unit is None or not unit.is_active:
            raise HTTPException(
                status_code=404, detail=f"Einzelinstanz {number} gibt es nicht.",
            )
        out.append((unit, number))
    return out


def held_by(db: Session, unit_ids: list[int]) -> dict[int, OrderUnit]:
    """Je Stück die **offene Zugehörigkeit**, falls es gerade in einem Auftrag läuft.

    Das ist die Exklusivität aus §3, von der Lese-Seite: höchstens eine Zeile je Stück
    kann offen sein, der partielle Unique-Index sorgt dafür. Was hier herauskommt, ist
    darum eindeutig – und es ist zugleich die **Verbindung**, aus der eine Abweichung
    entsteht (Abweichungsauftrag §3.2).
    """
    if not unit_ids:
        return {}
    rows: dict[int, OrderUnit] = {}
    for part in _chunks(list(unit_ids)):
        for m in (
            db.query(OrderUnit)
            .filter(OrderUnit.instance_unit_id.in_(part), OrderUnit.released_at.is_(None))
            .all()
        ):
            rows[m.instance_unit_id] = m
    return rows


def holders(db: Session, unit_ids: list[int]) -> dict[int, int]:
    """Je Stück die **Objektnummer des Auftrags**, in dem es gerade läuft.

    Zweite Form von ``held_by``, für die Anzeige: dort zählt nicht die Zeile, sondern
    wohin der Klick führt. Ein Stück «Im Prozess» ohne den Weg zu seinem Auftrag ist
    eine Sackgasse – man sieht, dass es läuft, aber nicht wo.
    """
    memberships = held_by(db, unit_ids)
    if not memberships:
        return {}
    nrs = {
        o.id: o.object_id
        for o in db.query(Order)
        .filter(Order.id.in_({m.order_id for m in memberships.values()}))
        .all()
    }
    return {uid: nrs[m.order_id] for uid, m in memberships.items() if m.order_id in nrs}


def _assert_may_leave(db: Session, membership: OrderUnit, number: str) -> None:
    """►►► Die markierte Stelle zur offenen Frage (Abweichungsauftrag §5) ◄◄◄

    **Darf das Stück den Modultyp verlassen, vor dem es gerade steht?** Die Antwort
    steht am **Modultyp** (``domain/modules.Module.units_may_leave``), nicht hier: eine
    globale Regel wäre für die reversible Datenerfassung zu streng und für einen
    künftigen Einkauf/Verkauf zu lasch.

    Solange die Entscheidung aussteht, ist dies die **einzige** Stelle, die sie liest –
    ein neuer Modultyp mit Aussenwirkung setzt das Flag und bekommt die Sperre geschenkt.
    """
    if membership.current_step_id is None:
        return
    step = db.query(ProcessStep).filter(ProcessStep.id == membership.current_step_id).first()
    if step is None:
        return
    module = modules.get(step.module_type)
    if module.units_may_leave:
        return
    raise HTTPException(
        status_code=409,
        detail=(
            f"Einzelinstanz {number} steht vor «{module.label}» und kann dort nicht "
            f"herausgenommen werden – dieses Modul wirkt nach aussen. Der Vorgang muss "
            f"dort erst abgeschlossen oder storniert werden."
        ),
    )


def _assert_as_picked(
    db: Session,
    line: "_Line",
    pairs: list[tuple[InstanceUnit, str]],
    held: dict[int, OrderUnit],
) -> None:
    """**Die Auswahl muss noch die sein, die der Mensch getroffen hat.**

    Zwischen Auswahl und Freigabe liegt Zeit, und in der kann jemand anders dasselbe Stück
    nehmen. Der partielle Unique-Index (§3) verhindert, dass beide es halten – er sagt aber
    nicht, **wer** es verliert. Ohne diese Prüfung entschied das die Reihenfolge der Klicks:
    ein als frei gewähltes Stück, das inzwischen lief, machte die Freigabe **still** zur
    Abweichung und entzog es dem anderen Auftrag, mit ``return_to = NULL`` – also für immer.

    Es ist optimistisches Sperren, und der Vergleichswert ist die Absicht selbst
    (``UnitPick.from_order``): «frei» oder «aus Auftrag N». Weicht die Wirklichkeit ab,
    passiert **nichts**, und der Fehler nennt beide Seiten. Ein Auftrag darf nie
    unbemerkt seine Art ändern.
    """
    stated = dict(line.picks)
    holders = {
        m.instance_unit_id: o.object_id
        for m, o in (
            db.query(OrderUnit, Order)
            .join(Order, Order.id == OrderUnit.order_id)
            .filter(OrderUnit.id.in_([m.id for m in held.values()]))
            .all()
        )
    } if held else {}

    stale: list[dict[str, Any]] = []
    for unit, number in pairs:
        was = stated.get(number)
        now = holders.get(unit.id)
        if was != now:
            stale.append({"number": number, "picked_from": was, "now_in": now})
    if not stale:
        return

    def where(order_object_id: Optional[int]) -> str:
        return f"in Auftrag {order_object_id}" if order_object_id else "frei"

    lines = [
        f"{s['number']}: bei der Auswahl {where(s['picked_from'])}, "
        f"jetzt {where(s['now_in'])}"
        for s in stale
    ]
    raise HTTPException(
        status_code=409,
        detail={
            "code": "pick_stale",
            "message": (
                ("Eine Einzelinstanz hat " if len(stale) == 1
                 else f"{len(stale)} Einzelinstanzen haben ")
                + "seit der Auswahl den Auftrag gewechselt – "
                + "; ".join(lines)
                + ". Die Auswahl ist veraltet – bitte prüfen und erneut freigeben."
            ),
            "units": stale,
        },
    )


def release(
    db: Session,
    *,
    lines: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    actor_id: Optional[int],
) -> Order:
    """Freigeben = den Prozess starten. **Eine Transaktion**, feste Reihenfolge (§6.3).

    **Jede Prüfung liegt vor der ersten Objektnummer.** Das ist keine Kosmetik: eine
    Sequence ist absichtlich nicht transaktional, ein Rollback danach liesse eine Lücke.
    Ein abgebrochener Freigabe-Versuch verbraucht darum keine Nummer – der einzige
    Ausnahmefall bleibt der echte Parallelzugriff, den erst der Unique-Index abfängt.
    """
    from .objects import next_object_id

    # ── 1. Alles prüfen, was ohne Nummer prüfbar ist ─────────────────────────
    resolved = resolve_lines(db, lines)
    effective = steps_for(db, resolved, steps)

    total = sum(ln.quantity for ln in resolved)
    missing = assert_releasable(total, effective)
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Auftrag ist noch nicht freigebbar – es fehlt: "
                   + ", ".join(missing) + ".",
        )
    for step in effective:
        st.assert_known(step["status_before"], field="Vorher-Status")
        st.assert_known(step["status_after"], field="Nachher-Status")

    end_status = st.DEFAULT_END_STATUS
    chain.assert_closes(effective)

    # Bestehende Stücke auflösen: frei übernehmen oder **aus einem laufenden Auftrag**
    # herüberholen. Beides führt durch dasselbe Start-Objekt (§4.1) – der Status eines
    # Stücks sagt, ob es in EINEM Prozess ist, nicht in welchem. Ein Wechsel des Auftrags
    # ändert ihn darum gar nicht: «Im Prozess» bleibt «Im Prozess».
    seen: set[str] = set()
    for ln in resolved:
        if ln.origin != LAGER:
            continue
        pairs = _resolve_units(db, [n for n, _ in ln.picks], seen=seen)
        held = held_by(db, [u.id for u, _ in pairs])
        _assert_as_picked(db, ln, pairs, held)
        for unit, number in pairs:
            source = held.get(unit.id)
            if source is None:
                # **Darf ein Auftrag dieses Stück greifen?** Die Antwort steht am Status
                # (``selectable``), nicht als Liste hier: ein gesperrtes Stück ja – das
                # Greifen IST das Aufheben der Sperre –, ein verschrottetes nie, denn es
                # gibt das Ding nicht mehr.
                if not st.is_selectable(unit.status):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Einzelinstanz {number} ist «{st.label(unit.status)}» – "
                            f"sie gibt es physisch nicht mehr und kann in keinem Auftrag "
                            f"mehr vorkommen."
                        ),
                    )
            else:
                _assert_may_leave(db, source, number)
                ln.taken[unit.id] = source
        ln.units = [u for u, _ in pairs]

    # Der Plan muss aufgehen, bevor er etwas kostet (§2, harte Invariante).
    planned: list[tuple[int, int, str]] = []
    for ln in resolved:
        if ln.origin == NEU:
            # Rein arithmetisch – prüft die Serialisierung, ohne eine Nummer zu ziehen.
            count, each = materialize.plan(ln.article.serialization, ln.quantity)
            planned.append((ln.quantity, count * each, ln.label))
        else:
            planned.append((ln.quantity, len(ln.units), ln.label))
    materialize.assert_quantity(planned, code=400)

    # ── 2. Ab hier werden Nummern vergeben ───────────────────────────────────
    object_id = next_object_id(db, "order")
    order = Order(
        object_id=object_id,
        # Der Name entsteht im selben Zug wie die Nummer – vorher gibt es keine, und
        # «Ohne Bezeichnung» im Kopf eines laufenden Auftrags ist keine Auskunft.
        name=f"Auftrag {object_id}",
        end_status=end_status,
    )
    db.add(order)
    db.flush()

    for ln in resolved:
        db.add(OrderLine(
            order_id=order.id, position=ln.position, article_id=ln.article.id,
            quantity=ln.quantity, origin=ln.origin,
        ))

    rows: list[ProcessStep] = []
    for position, step in enumerate(effective, start=1):
        row = ProcessStep(
            order_id=order.id,
            position=position,
            module_type=step["module_type"],
            status_before=step["status_before"],
            status_after=step["status_after"],
            config=step.get("config"),
            source_article_id=step.get("source_article_id"),
            source_version=step.get("source_version"),
        )
        db.add(row)
        rows.append(row)
    db.flush()

    # ── 3. Neue Stücke erzeugen – die EINZIGE Stelle, an der das passiert ────
    for ln in resolved:
        if ln.origin == NEU:
            ln.units = materialize.create_for_line(
                db, article=ln.article, quantity=ln.quantity,
            )

    # Und jetzt das Ergebnis gegen dieselbe Invariante halten.
    materialize.assert_quantity(
        [(ln.quantity, len(ln.units), ln.label) for ln in resolved], code=500,
    )

    # ── 3b. Übernahme: die Stücke verlassen ihren bisherigen Auftrag ─────────
    # **Vor** dem Anlegen der neuen Zeilen – der partielle Unique-Index lässt genau eine
    # offene Zugehörigkeit je Stück zu, und er prüft je Anweisung, nicht erst am Ende.
    _hand_over(db, order=order, lines=resolved, actor_id=actor_id)

    # ── 4./5. Die Stücke passieren das Start-Objekt, jedes mit eigenem Log-Eintrag ──
    all_units = [u for ln in resolved for u in ln.units]
    db.execute(
        insert(OrderUnit),
        [
            {
                "order_id": order.id,
                "instance_unit_id": u.id,
                # **Die Verbindung.** Sie entsteht hier und nirgends sonst: gekappt
                # (``None``) heisst, der Quell-Auftrag läuft mit weniger Stücken weiter.
                "return_to_order_id": (
                    ln.taken[u.id].order_id if (ln.returns and u.id in ln.taken) else None
                ),
            }
            for ln in resolved for u in ln.units
        ],
    )
    db.flush()
    membership_ids = [
        int(i) for (i,) in db.query(OrderUnit.id).filter(OrderUnit.order_id == order.id).all()
    ]
    _pass(
        db, order=order, units=all_units, membership_ids=membership_ids,
        kind=KIND_START, step=None,
        status_after=st.START_AFTER, next_step_id=rows[0].id, actor_id=actor_id,
    )

    # ── 6. Das erste Modul ist damit aktiv (abgeleitet: dort stehen die Stücke) ──
    # Und weil die Stücke jetzt davorstehen, wird hier die Stichprobe gezogen: **beim
    # Erreichen des Moduls**, nicht beim Modellieren (§2 – vorher steht die Menge nicht
    # fest). Gezogen wird über die **Gesamtmenge** des Auftrags, nicht je Instanz.
    sampling.ensure(db, order=order, step=rows[0], actor_id=actor_id)
    return order


def _hand_over(db: Session, *, order: Order, lines: list[_Line],
               actor_id: Optional[int]) -> None:
    """Übernommene Stücke aus ihrem bisherigen Auftrag herauslösen.

    Zwei Dinge, beide unverzichtbar:

    1. **Die Zeile des Quell-Auftrags wird geschlossen** – aber ``current_step_id``
       bleibt stehen. Das ist die Rückkehrposition; sie braucht kein eigenes Feld, denn
       «wo steht dieses Stück» ist genau die Frage, die diese Spalte beantwortet.
    2. **Der Quell-Auftrag bekommt seinen Log-Eintrag.** Ohne ihn bräche seine Historie
       mitten im Ablauf ab: das Stück wäre einfach weg. Der Status des Stücks ändert
       sich dabei nicht – es verlässt einen Prozess und tritt in einen anderen.
    """
    taken: list[tuple[OrderUnit, InstanceUnit]] = [
        (ln.taken[u.id], u) for ln in lines for u in ln.units if u.id in ln.taken
    ]
    if not taken:
        return
    db.execute(
        insert(ProcessEvent),
        [
            {
                "order_id": m.order_id,
                "step_id": m.current_step_id,
                "instance_unit_id": u.id,
                "kind": KIND_HANDOVER,
                "status_before": u.status,
                "status_after": u.status,
                "payload": {"to_order": order.object_id},
                "actor_id": actor_id,
            }
            for m, u in taken
        ],
    )
    now = datetime.now(timezone.utc)
    for part in _chunks([m.id for m, _ in taken]):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(released_at=now)
            .execution_options(synchronize_session=False)
        )
    for m, _ in taken:
        m.released_at = now


# ---------------------------------------------------------------------------
# Schritt bestätigen
# ---------------------------------------------------------------------------

def _verified_instance(db: Session, *, order: Order, step: ProcessStep,
                       instance_object_id: Optional[int],
                       verification: Optional[str]) -> Optional[Instance]:
    """**Habe ich das richtige Ding vor mir?** — die Scan-Pflicht, serverseitig.

    Der Scan verifiziert die **Instanz**, nicht die Einzelinstanz — und das ist keine
    Vereinfachung, sondern die einzige Möglichkeit: eine Einzelinstanz zieht bewusst
    keine Objektnummer (``models/instance_unit``), ein Etikett kann es für sie also gar
    nicht geben. Das physische Etikett klebt am physischen Ding, und das Ding **ist** die
    Instanz – die Kiste, die Maschine.

    Daraus fällt der Unterschied Charge ↔ Einzelserialisierung von selbst heraus, ohne
    eine einzige Abfrage danach (``materialize.plan``)::

        Charge, Menge 3              →  (1, 3)  eine Instanz   →  EIN Scan
        Einzelserialisierung, Menge 3 → (3, 1)  drei Instanzen →  DREI Scans

    Ein Vorgang je Instanz, ein Scan je Vorgang. Deshalb nimmt diese Ausführungsstelle
    genau **eine** Instanz entgegen und nicht «alles, was davorsteht».
    """
    module = modules.get(step.module_type)
    if not module.requires_verification:
        return None
    if verification not in VERIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{modules.label(step.module_type)}» verlangt, dass die Instanz vor der "
                f"Eingabe bestätigt wird – gescannt oder von Hand eingegeben. Ohne diese "
                f"Angabe steht nicht fest, an welchem Ding gearbeitet wurde."
            ),
        )
    instance = (
        db.query(Instance).filter(Instance.object_id == instance_object_id).first()
        if instance_object_id else None
    )
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Instanz {instance_object_id} gibt es nicht – es wurde nichts erfasst.",
        )
    return instance


def confirm_step(
    db: Session, *, order: Order, step_id: int, values: dict[str, Any],
    actor_id: Optional[int],
    instance_object_id: Optional[int] = None,
    verification: Optional[str] = None,
) -> dict[str, Any]:
    """«Bestätigen» — der eine Mechanismus, den jedes Modul auslöst.

    Prüft die Verifikation, prüft den Vorher-Status, lässt das Modul festhalten was es
    festhält, setzt den Nachher-Status, loggt, rückt vor. Ist der Schritt der letzte,
    passiert das Stück im selben Zug das **Ende-Objekt** und wird frei.

    **Ein Vorgang ist EINE Instanz** (§3): der Scan verifiziert sie, die Erfassung gilt
    für ihre gezogenen Stücke, und das Urteil betrifft sie. Bei mehreren Instanzen vor
    dem Modul sind es mehrere Vorgänge – bei einer Charge einer.

    **Die Erfassung liegt VOR dem Statuswechsel.** Fehlt ein Pflichtpunkt, ist das ein
    Fehler mit Namen – und es hat sich nichts bewegt. Andersherum stünde die Erfassung
    unter Zugzwang: das Stück wäre schon vorgerückt, und der einzige Weg zurück wäre
    keiner.

    **«Nicht bestanden» rückt NICHT vor** (§4). Die Feststellung ist geloggt und
    eingefroren, die Stücke bleiben an ihrem Zustandspunkt stehen, und was daraus folgt,
    entscheidet ein Mensch. Ein automatisch angelegter Folgeauftrag wäre ein leerer
    Entwurf, den niemand bestellt hat – und er zöge Stücke aus dem Auftrag, ohne dass
    jemand zugestimmt hätte. Stilles Weiterlaufen ist der Fehler, den es zu verhindern
    gilt; das Anhalten ist nicht der Nebeneffekt, sondern der Zweck.
    """
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    if order_status(db, order) != st.IM_PROZESS:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Auftrag ist «{st.label(order_status(db, order))}» – "
                    f"es gibt nichts mehr zu bestätigen."),
        )
    module = modules.get(step.module_type)
    instance = _verified_instance(
        db, order=order, step=step,
        instance_object_id=instance_object_id, verification=verification,
    )

    # ►► **Die Sperre — hier und nur hier.** ◄◄
    #
    # Sie steht am EINEN Ausführungs-Mechanismus, den jedes Modul auslöst, und nicht in
    # einem Modul. Ein neuer Modultyp erbt sie damit, ohne eine Zeile dafür zu schreiben –
    # er fragt gar nicht, ob er darf, ihm wird gesagt, dass er nicht darf.
    blocked = pending_returns(db, order).get(step.id)
    if blocked:
        raise HTTPException(
            status_code=409,
            detail=(
                f"«{modules.label(step.module_type)}» wartet auf die Rückführung aus "
                + ("Auftrag " if len(blocked) == 1 else "den Aufträgen ")
                + ", ".join(str(n) for n in blocked)
                + ". Solange dort etwas offen ist, gehört es zu dem, was hier bearbeitet "
                  "wird – bestätigen hiesse ohne dieses Stück fortzufahren."
            ),
        )

    waiting = _units_at(db, order, step.id, instance_id=instance.id if instance else None)
    if not waiting:
        where = f" von Instanz {instance.object_id}" if instance else ""
        raise HTTPException(
            status_code=409,
            detail=(f"Vor «{modules.label(step.module_type)}» steht keine Einzelinstanz"
                    f"{where} – hier ist gerade nichts zu tun."),
        )

    following = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.position > step.position)
        .order_by(ProcessStep.position)
        .first()
    )

    for membership, unit in waiting:
        if unit.status != step.status_before:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Einzelinstanz {_number(db, unit)} steht auf "
                    f"«{st.label(unit.status)}», «{modules.label(step.module_type)}» erwartet "
                    f"«{st.label(step.status_before)}»."
                ),
            )

    units = [u for _, u in waiting]
    membership_ids = [m.id for m, _ in waiting]

    # **Wer wird erfasst?** Die gezogene Stichprobe – einmal gezogen, eingefroren im Log.
    # Das Netz hier ist idempotent: gibt es die Ziehung schon, passiert nichts.
    sampling.ensure(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    drawn_ids = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    drawn = [u for u in units if u.id in drawn_ids]

    # Was das Modul festhält, hängt am **Stück** – ein Wertesatz, eine Zeile je gezogener
    # Einzelinstanz (siehe ``capture.record_for_step``). Die **nicht** gezogenen laufen
    # ohne Erfassung durch; sichtbar ist das, weil sie keinen ``capture``-Eintrag haben.
    captures = capture_svc.record_for_step(
        db, order=order, step=step, units=drawn, values=values, actor_id=actor_id,
    )
    result = next((c.result for c in captures.values()), None)
    if captures:
        db.execute(
            insert(ProcessEvent),
            [
                {
                    "order_id": order.id, "step_id": step.id, "instance_unit_id": u.id,
                    "kind": KIND_CAPTURE,
                    # Erfassen ist keine Zustandsänderung – gemessen wird, was da ist.
                    "status_before": u.status, "status_after": u.status,
                    "payload": {
                        "capture_id": captures[u.id].id,
                        "result": result,
                        "verification": verification,
                    },
                    "actor_id": actor_id,
                }
                for u in drawn
            ],
        )

    # **Nicht bestanden ⇒ nichts rückt vor.** Auch die nicht gezogenen Stücke dieser
    # Instanz bleiben stehen: fällt die Stichprobe durch, ist sie nicht mehr
    # repräsentativ, und der ungeprüfte Rest ist verdächtig (§4.1). Ihn weiterlaufen zu
    # lassen hiesse, ihn hinterher wieder einsammeln zu müssen.
    if result == "failed":
        db.flush()
        return {"moved": 0, "held": len(units), "result": result}

    _pass(
        db, order=order, units=units, membership_ids=membership_ids,
        kind=KIND_STEP, step=step,
        status_after=step.status_after,
        next_step_id=following.id if following else None,
        actor_id=actor_id,
        # **Wie wurde bestätigt?** Am Schritt-Ereignis, nicht nur an der Erfassung: ein
        # Modul ohne Erfassungspunkte (Verschrotten) hat sonst keinen Beleg dafür – und
        # gerade dort ist er am wichtigsten, weil der Vorgang endgültig ist.
        payloads={u.id: {"verification": verification} for u in units},
    )
    # ►► **Ein terminales Modul IST der Ausgang.** ◄◄
    #
    # ``_pass`` hat die Zugehörigkeit gerade geschlossen (``next_step_id=None``) und den
    # Zielzustand gesetzt – mehr passiert nicht. Insbesondere **nicht** das Ende-Objekt:
    # dort hängt die Rückführung, und ein ausgesondertes Stück kehrt nirgends zurück.
    #
    # Damit ist §3 des Auftrags erfüllt, ohne eine Zeile Wartelogik: der Quell-Auftrag
    # zählt seine Ausleihen über die **offene** Zeile (``waiting_counts``), und die gibt
    # es nicht mehr. Er wartet nicht, sein Modul ist nicht gesperrt, und bleibt ihm
    # nichts, ist sein Ziel unerreichbar – genau wie bei einer gekappten Rückführung.
    if module.terminal:
        db.flush()
        return {"moved": len(units), "held": 0, "result": result}

    if following is None:
        _finish(db, order=order, rows=waiting, actor_id=actor_id)
    else:
        # Angekommen am nächsten Modul – dort wird jetzt gezogen (§2: beim Erreichen,
        # denn vorher steht die Menge nicht fest).
        sampling.ensure(db, order=order, step=following, actor_id=actor_id)
    db.flush()
    return {"moved": len(units), "held": 0, "result": result}


def _finish(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
            actor_id: Optional[int]) -> None:
    """Das Ende-Objekt. **Es setzt den Endzustand — es sei denn, das Stück geht weiter.**

    Das ist eine Regel, keine Fallunterscheidung: das Ende-Objekt reicht das Stück an
    den weiter, der als Nächstes kommt. Kommt niemand, wird es frei (``end_status``,
    §4.2). Kommt der Auftrag, aus dem es geliehen war, bleibt es **Im Prozess** – es ist
    ja in einem.

    Die Stücke bewegen sich dabei in **Gruppen mit gleichem Ziel**, nicht einzeln: ein
    Auftrag kann geliehene und eigene Stücke gleichzeitig ans Ende bringen.
    """
    back = [(m, u) for m, u in rows if m.return_to_order_id]
    stay = [(m, u) for m, u in rows if not m.return_to_order_id]

    for group, status_after in ((stay, order.end_status), (back, st.IM_PROZESS)):
        if not group:
            continue
        _pass(
            db, order=order,
            units=[u for _, u in group], membership_ids=[m.id for m, _ in group],
            kind=KIND_END, step=None,
            status_after=status_after, next_step_id=None, actor_id=actor_id,
        )
    if back:
        _return_home(db, order=order, rows=back, actor_id=actor_id)


def _return_home(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
                 actor_id: Optional[int]) -> None:
    """Geliehene Stücke kehren an **genau die Stelle** zurück, an der sie ausgeschert sind.

    Die Stelle steht bereits da: die Zeile des Quell-Auftrags wurde beim Ausscheren
    geschlossen, ihr ``current_step_id`` aber nicht angetastet. Sie wieder zu öffnen
    **ist** die Rückführung – es gibt nichts nachzuschlagen und nichts zu berechnen.

    Möglich ist das erst hier, weil die Zeile dieses Auftrags eine Anweisung vorher
    geschlossen wurde: der partielle Unique-Index lässt genau eine offene Zugehörigkeit
    je Stück zu, und er prüft je Anweisung.
    """
    homes = {
        (m.order_id, m.instance_unit_id): m
        for m in (
            db.query(OrderUnit)
            .filter(
                OrderUnit.order_id.in_({m.return_to_order_id for m, _ in rows}),
                OrderUnit.instance_unit_id.in_({u.id for _, u in rows}),
                OrderUnit.released_at.isnot(None),
                OrderUnit.current_step_id.isnot(None),
            )
            .order_by(OrderUnit.id)
            .all()
        )
    }
    events: list[dict[str, Any]] = []
    reopen: list[int] = []
    for m, u in rows:
        home = homes.get((m.return_to_order_id, u.id))
        if home is None:
            # Die Verbindung zeigt ins Leere. Das darf nicht sein und wird nicht
            # stillschweigend überspielt: ein Stück, das nirgends ankommt, wäre für
            # jeden Bestand und jede Historie ein Loch.
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Einzelinstanz {_number(db, u)} sollte in Auftrag "
                    f"{m.return_to_order_id} zurückkehren, findet dort aber keine offene "
                    f"Stelle – der Datenbestand ist kaputt."
                ),
            )
        reopen.append(home.id)
        events.append({
            "order_id": home.order_id,
            "step_id": home.current_step_id,
            "instance_unit_id": u.id,
            "kind": KIND_RETURN,
            "status_before": st.IM_PROZESS,
            "status_after": st.IM_PROZESS,
            "payload": {"from_order": order.object_id},
            "actor_id": actor_id,
        })
    db.execute(insert(ProcessEvent), events)
    for part in _chunks(reopen):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(released_at=None)
            .execution_options(synchronize_session=False)
        )


# ---------------------------------------------------------------------------
# Ableitungen (Ebene 2 lesen)
# ---------------------------------------------------------------------------

def _units_at(db: Session, order: Order, step_id: Optional[int],
              *, instance_id: Optional[int] = None):
    """Was steht an diesem Zustandspunkt — wahlweise nur die Stücke **einer** Instanz.

    Die Einschränkung ist die Ausführungsseite der Scan-Regel: verifiziert wird eine
    Instanz, also arbeitet ein Vorgang auch nur an ihren Stücken.
    """
    q = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.is_(None),
            OrderUnit.current_step_id == step_id,
        )
    )
    if instance_id is not None:
        q = q.filter(InstanceUnit.instance_id == instance_id)
    return q.order_by(OrderUnit.id).all()


def step_work(db: Session, order: Order, step: ProcessStep) -> list[dict[str, Any]]:
    """**Was ist an diesem Modul zu tun — je Instanz?**

    Ein Vorgang ist eine Instanz (§3), also ist das hier die Arbeitsliste: eine Zeile je
    Instanz, die davorsteht. Sie trägt alles, was die Oberfläche braucht, ohne dass sie
    etwas ableitet:

    ``waiting``   wie viele Stücke dieser Instanz hier stehen
    ``sample``    wie viele davon **gezogen** sind (die übrigen laufen ohne Erfassung durch)
    ``held``      hat die letzte Erfassung **nicht bestanden**? Dann rückt hier nichts vor
    ``rest``      die ungeprüften Stücke **dieser** Instanz an **diesem** Modul

    ``rest`` ist der «Rest» aus §4.1 – und zwar genau in dem Umfang, den er haben darf:
    die Stücke, die hier im Prozess stehen. **Nicht** die übrige Charge: Stücke, die
    anderswo laufen oder längst am Lager liegen, hat dieses Modul nie behandelt, und eine
    100 %-Kontrolle über sie wäre eine Aussage über Material, das hier nie war.

    Das ``held`` ist die **letzte** Erfassung, nicht irgendeine: kommt ein Stück nach einer
    Abweichung zurück und wird erneut erfasst, zählt das neue Urteil. Ein Hold, den nur ein
    alter Befund am Leben hält, wäre eine Sackgasse ohne Ausgang.
    """
    waiting = _units_at(db, order, step.id)
    if not waiting:
        return []
    units = [u for _, u in waiting]
    # **Gezogen** kommt aus dem Log, **erfasst** aus den Werten – zwei verschiedene
    # Fragen. Wer «gezogen» aus dem Vorhandensein einer Erfassung ableitet, meldet vor
    # der ersten Eingabe eine leere Stichprobe und einen Rest, der alles umfasst.
    drawn = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    latest = _latest_captures(db, order, step, [u.id for u in units])
    numbers = unit_numbers(db, units)

    instances = {
        i.id: i
        for i in db.query(Instance).filter(Instance.id.in_({u.instance_id for u in units})).all()
    }
    articles = {
        a.id: a.name
        for a in db.query(Article)
        .filter(Article.id.in_({i.article_id for i in instances.values()}))
        .all()
    } if instances else {}

    groups: dict[int, dict[str, Any]] = {}
    for unit in units:
        instance = instances.get(unit.instance_id)
        if instance is None:
            raise HTTPException(
                status_code=500,
                detail=f"Einzelinstanz {unit.id} hat keine Instanz – der Datenbestand ist kaputt.",
            )
        row = groups.setdefault(instance.id, {
            "instance_object_id": instance.object_id,
            "article_name": articles.get(instance.article_id),
            "waiting": 0, "sample": 0, "rest": 0, "held": False,
            "failed_numbers": [],
        })
        row["waiting"] += 1
        if unit.id in drawn:
            row["sample"] += 1
        else:
            row["rest"] += 1
        capture = latest.get(unit.id)
        if capture is not None and capture.result == "failed":
            row["held"] = True
            row["failed_numbers"].append(numbers[unit.id])
    return [groups[i] for i in sorted(groups)]


def _latest_captures(db: Session, order: Order, step: ProcessStep,
                     unit_ids: list[int]) -> dict[int, Any]:
    """Je Stück die **jüngste** Erfassung an diesem Modul. Ältere zählen nicht mehr."""
    from ..models import Capture

    out: dict[int, Any] = {}
    if not unit_ids:
        return out
    for part in _chunks(list(unit_ids)):
        for row in (
            db.query(Capture)
            .filter(
                Capture.order_id == order.id,
                Capture.step_id == step.id,
                Capture.instance_unit_id.in_(part),
            )
            .order_by(Capture.id)
            .all()
        ):
            out[row.instance_unit_id] = row   # die letzte gewinnt
    return out


def held_numbers(db: Session, order: Order, step: ProcessStep, *,
                 instance_object_id: int, group: str) -> list[str]:
    """Die Nummern einer Entscheidungs-Gruppe — **erst auf Klick**, nie auf Vorrat.

    ``failed`` sind die durchgefallenen (die Stichprobe), ``rest`` die ungeprüften
    Stücke derselben Instanz an diesem Modul. Beide Listen gehen als Vorauswahl in einen
    ganz gewöhnlichen Auftragsentwurf – **kein neuer Mechanismus** (§4.1), nur eine
    andere Vorbelegung.

    Sie stehen bewusst nicht in der Auftrags-Antwort: bei einer 6000er-Charge wäre der
    «Rest» sechstausend Nummern, mitgeliefert bei jedem Öffnen des Auftrags.
    """
    instance = (
        db.query(Instance).filter(Instance.object_id == instance_object_id).first()
    )
    if instance is None:
        raise HTTPException(
            status_code=404, detail=f"Instanz {instance_object_id} gibt es nicht.",
        )
    waiting = _units_at(db, order, step.id, instance_id=instance.id)
    units = [u for _, u in waiting]
    if group == "failed":
        latest = _latest_captures(db, order, step, [u.id for u in units])
        chosen = [u for u in units if (latest.get(u.id) is not None
                                       and latest[u.id].result == "failed")]
    elif group == "rest":
        # **Ungeprüft = nicht gezogen** – dieselbe Quelle wie die Zahl daneben.
        drawn = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
        chosen = [u for u in units if u.id not in drawn]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"«{group}» ist keine Gruppe – erlaubt: failed, rest.",
        )
    numbers = unit_numbers(db, chosen)
    return [numbers[u.id] for u in chosen]


def _open_memberships(db: Session, order: Order) -> list[OrderUnit]:
    return (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .all()
    )


def _number(db: Session, unit: InstanceUnit) -> str:
    instance = db.query(Instance).filter(Instance.id == unit.instance_id).first()
    if instance is None:
        raise HTTPException(
            status_code=500,
            detail=f"Einzelinstanz {unit.id} hat keine Instanz – der Datenbestand ist kaputt.",
        )
    return unit_number(instance, unit)


def steps_of(db: Session, order: Order) -> list[ProcessStep]:
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id)
        .order_by(ProcessStep.position)
        .all()
    )


def lines_of(db: Session, order: Order) -> list[OrderLine]:
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id)
        .order_by(OrderLine.position)
        .all()
    )


def units_page(db: Session, order: Order, *, membership_ids: list[int],
               limit: int, offset: int) -> tuple[list[tuple[OrderUnit, InstanceUnit]], int]:
    """Die einzelnen Stücke einer Position – auf Abruf und in Seiten.

    **Welche** Stücke, entscheidet nicht diese Abfrage, sondern die Zuordnung im
    Prozessbild (``flow.units_on``): sie kommen als Zeilen-ids herein. Eine eigene
    Bedingung hier wäre eine zweite Antwort auf «wo steht dieses Stück» – und genau
    daraus entstand der Widerspruch zwischen Pille und Liste (Befund 2.1).
    """
    if not membership_ids:
        return [], 0
    q = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id == order.id, OrderUnit.id.in_(membership_ids))
    )
    total = q.count()
    return q.order_by(OrderUnit.id).limit(limit).offset(offset).all(), total


# ---------------------------------------------------------------------------
# Der Auftragsstatus — ABGELEITET, an genau einer Stelle
# ---------------------------------------------------------------------------
#
# Ein Auftrag hat genau drei Zustände, und keiner davon wird gesetzt: er ergibt sich aus
# dem Zustand seiner Einzelinstanzen. Eine Spalte daneben wäre der zweite Ort — und der
# läuft beim ersten vergessenen Update weg. «Freigegeben» kommt nicht vor: Freigeben ist
# die Aktion, mit der der Auftrag entsteht, kein Zustand, in dem er verweilt.
#
#   Im Prozess      es ist noch etwas unterwegs
#   Abgeschlossen   mindestens ein Stück hat das Ziel erreicht
#   Abgebrochen     nichts kann das Ziel mehr erreichen
#
# Zwei Formen derselben Regel, nebeneinander im selben Modul: ``order_status`` für einen
# geladenen Auftrag, ``order_statuses`` für den Feed (EINE Abfrage, kein N+1).

def _derive(arrived: int, alive: int, lent: int) -> str:
    """Die Regel selbst — aus drei Zahlen. Alles andere zählt nur.

    **Was noch unterwegs ist, gewinnt.** Ein Auftrag, dessen eines Stück angekommen und
    dessen anderes gerade in einer Abweichung ist, läuft – er ist nicht «Abgeschlossen».
    Vorher stand die Ankunft zuerst; das fiel nicht auf, weil Stücke ohne Abweichungen im
    Gleichschritt laufen und ein Auftrag darum nie halb fertig war.

    ``lent`` sind die Stücke, die einer Abweichung geliehen sind und **zurückkommen**
    (Abweichungsauftrag §3.2). Gekappte Verbindungen zählen hier nicht: sie kommen nicht
    zurück, der Auftrag läuft mit weniger weiter – und bleibt nichts übrig, ist sein Ziel
    unerreichbar.
    """
    if alive or lent:
        return st.IM_PROZESS
    if arrived:
        return st.ABGESCHLOSSEN
    # Nichts angekommen und nichts mehr unterwegs: das Ziel ist unerreichbar.
    return st.ABGEBROCHEN


def order_status(db: Session, order: Order) -> str:
    """Der Zustand **eines** Auftrags."""
    return order_statuses(db, [order.id]).get(order.id, st.IM_PROZESS)


def waiting_counts(db: Session, order_ids: list[int]) -> dict[int, int]:
    """Wie viele Stücke sind gerade **ausgeliehen und kommen zurück**? — je Auftrag.

    **Abgeleitet, nicht gespeichert.** Es wartet, wer noch mindestens eine offene
    rückführende Verbindung hat. Ein Zähler an der Zeile wäre ein zweiter Ort, an dem
    dieselbe Zahl steht – und der erste vergessene Rückweg liesse ihn stehen.

    **Die Kette zählt, nicht nur der direkte Nachbar** (§3.5): leiht A an B und B weiter
    an C, wartet auch A – das Stück ist unterwegs zu ihm, nur eine Stufe tiefer. Darum
    wird die Verbindung von der offenen Zeile aus **nach oben verfolgt**.

    Und daraus fällt der Grenzfall von selbst heraus: **kappt eine Stufe die Rückführung,
    endet die Kette dort** – niemand darüber wartet weiter. Das ist richtig, denn das
    Stück kommt nie mehr zurück; jeder in der Kette läuft dann mit weniger weiter, und
    wem nichts bleibt, dessen Ziel ist unerreichbar (§3.4, eine Stufe weiter gedacht).
    """
    if not order_ids:
        return {}
    # Alle laufenden Ausleihen. Das ist per Definition ein kleiner Satz – eine Abweichung
    # ist der Ausnahmefall, nicht der Normalbetrieb.
    open_loans = (
        db.query(OrderUnit.instance_unit_id, OrderUnit.return_to_order_id)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(
            OrderUnit.released_at.is_(None),
            OrderUnit.return_to_order_id.isnot(None),
            InstanceUnit.is_active.is_(True),
        )
        .all()
    )
    if not open_loans:
        return {}
    units = {int(u) for u, _ in open_loans}
    # Die Kette: von einem Auftrag aus gesehen, wohin er dieses Stück selbst zurückgibt.
    upward: dict[tuple[int, int], int] = {}
    for part in _chunks(sorted(units)):
        for m in (
            db.query(OrderUnit)
            .filter(
                OrderUnit.instance_unit_id.in_(part),
                OrderUnit.return_to_order_id.isnot(None),
            )
            .all()
        ):
            upward[(m.order_id, m.instance_unit_id)] = m.return_to_order_id

    wanted = set(order_ids)
    out: dict[int, int] = {}
    for unit, target in open_loans:
        unit, oid = int(unit), int(target)
        seen: set[int] = set()
        while oid is not None and oid not in seen:
            seen.add(oid)
            if oid in wanted:
                out[oid] = out.get(oid, 0) + 1
            oid = upward.get((oid, unit))
    return out


def _away_points(db: Session, order: Order) -> dict[int, int]:
    """Je ausgeschertem Stück der Zustandspunkt, an dem es diesen Auftrag verlassen hat.

    Die Stelle steht schon da: beim Ausscheren wurde die Zeile geschlossen, ihr
    ``current_step_id`` aber nicht angetastet (§3.3). Nachzuschlagen gibt es nichts.
    """
    return {
        m.instance_unit_id: m.current_step_id
        for m in db.query(OrderUnit).filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.isnot(None),
            OrderUnit.current_step_id.isnot(None),
        ).all()
        if m.current_step_id is not None
    }


def returning_home(db: Session, order: Order) -> dict[int, int]:
    """Welche ausgescherten Stücke kehren **hierher** zurück? — ``{Stück: Halter-Auftrag}``.

    Die eine Stelle, an der die Rückführungs-**Kette** gelesen wird (§3.5): leiht A an B
    und B weiter an C, kommt das Stück trotzdem zu A – nur eine Stufe tiefer. Gefolgt wird
    ``return_to_order_id``, die Eigenschaft der **Verbindung**; eine gekappte Ausleihe
    endet die Kette, und das ist die Aussage «kommt nie zurück».

    Zwei Fragen lesen sie: welches Modul **gesperrt** ist (``pending_returns``) und wo im
    Bild eine **Rückführungslinie** hingehört (``services/flow``). Zweimal gelaufen wären
    es zwei Ableitungen derselben Sache – und die eine hätte die Kette irgendwann nicht
    mehr gekannt.
    """
    at = _away_points(db, order)
    if not at:
        return {}
    holders = held_by(db, list(at))
    if not holders:
        return {}

    upward: dict[tuple[int, int], int] = {}
    for part in _chunks(list(at)):
        for m in (
            db.query(OrderUnit)
            .filter(
                OrderUnit.instance_unit_id.in_(part),
                OrderUnit.return_to_order_id.isnot(None),
            )
            .all()
        ):
            upward[(m.order_id, m.instance_unit_id)] = m.return_to_order_id

    out: dict[int, int] = {}
    for unit_id, holder in holders.items():
        target, seen = upward.get((holder.order_id, unit_id)), set()
        while target is not None and target not in seen:
            seen.add(target)
            if target == order.id:
                out[unit_id] = holder.order_id
                break
            target = upward.get((target, unit_id))
    return out


def pending_returns(db: Session, order: Order) -> dict[int, list[int]]:
    """**Worauf wartet welches Modul?** — Modul-id → Objektnummern der Abweichungen.

    Ein Stück, das an einem Zustandspunkt ausgeschert ist und **zurückkommt**, gehört zu
    dem, was an diesem Punkt bearbeitet wird. Solange es unterwegs ist, darf das Modul
    dahinter nicht laufen: bestätigen hiesse ohne dieses Stück fortzufahren – und
    hinterher wäre es zurück, aber der Zug abgefahren.

    **Gekappte Ausleihen sperren nichts.** Sie kommen nie zurück; der Auftrag läuft mit
    weniger Stücken weiter und wartet ausdrücklich nicht (§3.4). Ohne diese Unterscheidung
    stünde jedes Modul, aus dem je etwas ausgesondert wurde, für immer still.

    **Die Kette zählt** (§3.5): leiht A an B und B weiter an C, wartet auch A – das Stück
    ist unterwegs zu ihm, nur eine Stufe tiefer. Genannt wird dabei der Auftrag, in dem es
    **jetzt** steckt: dort ist etwas zu tun, damit es weitergeht.

    Abgeleitet, nicht gespeichert – wie alles hier. Ein Sperr-Flag am Modul wäre ein
    zweiter Ort für dieselbe Aussage, und der erste vergessene Rückweg liesse ihn stehen.
    """
    coming = returning_home(db, order)
    if not coming:
        return {}
    at = _away_points(db, order)

    found: dict[int, set[int]] = {}
    for unit_id, holder_order_id in coming.items():
        step_id = at.get(unit_id)
        if step_id is None:
            continue
        found.setdefault(int(step_id), set()).add(holder_order_id)

    ids = {oid for group in found.values() for oid in group}
    numbers = {
        o.id: o.object_id
        for o in db.query(Order).filter(Order.id.in_(ids)).all()
    }
    return {
        step_id: sorted(numbers[oid] for oid in group if oid in numbers)
        for step_id, group in found.items()
    }


def order_statuses(db: Session, order_ids: list[int]) -> dict[int, str]:
    """Der Zustand **vieler** Aufträge – für den Feed, ohne N+1.

    «Unterwegs» heisst: die Zugehörigkeit ist offen **und** das Stück gibt es noch. Ein
    deaktiviertes Stück kann nirgends mehr ankommen – ohne diese Bedingung hätte
    «Abgebrochen» keinen Erzeuger und wäre ein Wert, den nie jemand sieht.

    «Angekommen» heisst: die Zugehörigkeit ist geschlossen **und** das Stück steht vor
    keinem Modul mehr. Eine geschlossene Zeile allein genügt nicht – sie schliesst sich
    auch, wenn ein Stück ausschert (siehe ``OrderUnit``), und das ist das Gegenteil von
    angekommen.
    """
    if not order_ids:
        return {}
    rows = (
        db.query(
            OrderUnit.order_id,
            func.count(OrderUnit.id).filter(
                OrderUnit.released_at.isnot(None), OrderUnit.current_step_id.is_(None)
            ).label("arrived"),
            func.count(OrderUnit.id).filter(
                OrderUnit.released_at.is_(None), InstanceUnit.is_active.is_(True)
            ).label("alive"),
        )
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id.in_(order_ids))
        .group_by(OrderUnit.order_id)
        .all()
    )
    lent = waiting_counts(db, order_ids)
    found = {
        int(oid): _derive(int(a), int(al), lent.get(int(oid), 0))
        for oid, a, al in rows
    }
    # Ein Auftrag ohne jede Zugehörigkeit kann es nicht geben (die Freigabe verlangt
    # mindestens eine Einzelinstanz). Käme er doch vor, ist er kein «Im Prozess».
    return {oid: found.get(oid, st.ABGEBROCHEN) for oid in order_ids}


def deviation_flags(db: Session, order_ids: list[int]) -> dict[int, bool]:
    """Welche dieser Aufträge sind **Abweichungen**? — wörtlich die Frage aus §2.

    «Enthält ein Auftrag bei seiner Freigabe Einzelinstanzen, die zu diesem Zeitpunkt den
    Status *Im Prozess* haben» – und genau das steht im Log: sein Start-Eintrag trägt
    dann ``status_before = im_prozess`` statt ``freigegeben``.

    Es gibt **kein Feld** dafür und keinen Auftragstyp. Ein Abweichungsauftrag ist ein
    ganz gewöhnlicher Auftrag; «Abweichung» ist eine Auskunft über ihn, keine Eigenschaft,
    die jemand setzt.
    """
    if not order_ids:
        return {oid: False for oid in order_ids}
    hits = {
        int(oid)
        for (oid,) in db.query(ProcessEvent.order_id)
        .filter(
            ProcessEvent.order_id.in_(order_ids),
            ProcessEvent.kind == KIND_START,
            ProcessEvent.status_before == st.IM_PROZESS,
        )
        .distinct()
        .all()
    }
    return {oid: oid in hits for oid in order_ids}


def active_step_id(db: Session, order: Order) -> Optional[int]:
    """Welches Modul ist **jetzt** dran? Das erste, vor dem noch ein Stück steht.

    Abgeleitet, nicht gespeichert: ein zweites Feld dafür wäre eine zweite Wahrheit,
    die beim ersten vergessenen Update auseinanderläuft.
    """
    open_rows = _open_memberships(db, order)
    if not open_rows:
        return None
    waiting = {m.current_step_id for m in open_rows if m.current_step_id is not None}
    for step in steps_of(db, order):
        if step.id in waiting:
            return step.id
    return None


def events_page(db: Session, order: Order, *, limit: int) -> tuple[list[ProcessEvent], int]:
    """Die Historie – die **neuesten** ``limit`` Einträge und wie viele es insgesamt sind.

    Der Deckel wird ausgewiesen, nicht verschwiegen: bei 5000 Stück hat der Log 10 000
    Einträge, und eine Liste, die stumm bei 200 aufhört, sieht aus wie die ganze
    Wahrheit. Die Zahl daneben sagt, dass es mehr gibt.
    """
    total = (
        db.query(func.count(ProcessEvent.id))
        .filter(ProcessEvent.order_id == order.id)
        .scalar() or 0
    )
    rows = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.order_id == order.id)
        .order_by(ProcessEvent.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows)), int(total)


def started_at(db: Session, order: Order, unit_ids: list[int]) -> dict[int, datetime]:
    """**Wann hat dieses Stück das Start-Objekt passiert?** — je Stück, aus dem Log.

    Der Start ist ein Ereignis wie jedes andere, und sein Zeitstempel steht bereits im
    Log. Eine Spalte ``gestartet_am`` daneben wäre eine Kopie, die beim ersten Nacherfassen
    von der Wahrheit abweicht – und die Wahrheit ist der Log (§7.2).

    Gemeint ist der Eintritt in **diesen** Auftrag: ein Stück, das ausschert, passiert im
    Abweichungsauftrag ein zweites Start-Objekt, und dort ist «seit wann läuft es hier»
    eine andere Zahl als im Auftrag darüber.
    """
    if not unit_ids:
        return {}
    out: dict[int, datetime] = {}
    for part in _chunks(list(unit_ids)):
        for uid, at in (
            db.query(ProcessEvent.instance_unit_id, func.min(ProcessEvent.created_at))
            .filter(
                ProcessEvent.order_id == order.id,
                ProcessEvent.kind == KIND_START,
                ProcessEvent.instance_unit_id.in_(part),
            )
            .group_by(ProcessEvent.instance_unit_id)
            .all()
        ):
            out[int(uid)] = at
    return out


def unit_numbers(db: Session, units: Iterable[InstanceUnit]) -> dict[int, str]:
    """Nummern zu Einzelinstanzen — **eine** Abfrage, kein N+1."""
    units = list(units)
    if not units:
        return {}
    instances = {
        i.id: i
        for i in db.query(Instance)
        .filter(Instance.id.in_({u.instance_id for u in units}))
        .all()
    }
    out: dict[int, str] = {}
    for u in units:
        instance = instances.get(u.instance_id)
        if instance is None:
            raise HTTPException(
                status_code=500,
                detail=f"Einzelinstanz {u.id} hat keine Instanz – der Datenbestand ist kaputt.",
            )
        out[u.id] = unit_number(instance, u)
    return out
