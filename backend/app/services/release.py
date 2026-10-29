"""**Die Freigabe: ein Auftrag entsteht – als Ganzes, in einer Transaktion.**

Erst wird alles geprüft, was ohne Nummer prüfbar ist (``_checked`` – dieselbe Prüfung
beantwortet den Entwurf, ``orders.validate_draft``), dann entstehen Nummer, Zeilen,
Module und neue Stücke, und die Stücke passieren das Start-Objekt. Übernommene Stücke
verlassen dabei ihren bisherigen Auftrag (``_hand_over``).

Gelesen wird PROCESS_CORE.md; hier steht nur, was daraus folgt.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from ..domain import chain, modules, statuses as st
from ..models import (
    Article, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent,
    ProcessStep,
)
from ..models.order_line import LAGER, NEU, ORIGINS
from ..models.process_event import (
    KIND_HANDOVER, KIND_START,
)
from . import (
    article_process, articles as articles_svc, materialize,
    voucher as voucher_svc,
    places as places_svc, sampling,
)
from .instances import find_units
from .order_state import _chunks, held_by, holders
from .process import _join, _pass, _run_through, lock_orders


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
        # **Nur ein freigegebener Artikel erzeugt Neues** (``articles.may_create``).
        # Nur für «Neu»: bestehende Stücke eines ausgelaufenen Artikels müssen abwickelbar
        # bleiben, sonst wäre jedes davon eine Leiche, die sich nicht einmal aussondern
        # liesse. Die Regel steht in ``services/articles``; hier wird sie gefragt, nicht
        # nachgebaut.
        if origin == NEU:
            problem = articles_svc.may_create(article)
            if problem:
                raise HTTPException(status_code=400,
                                    detail=f"Zeile {position}: {problem}")
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
    """**Höchstens EINE «Neu»-Zeile** – daneben beliebig viele «Lager»-Zeilen.

    Ein Erzeugungsauftrag fährt die **Vorlage des Artikels**, als Kopie mit
    Versionsstempel (§2.1). Der Stempel sagt «diese Stücke sind genau so entstanden, wie
    Artikel X es beschreibt» – und die Frage, *welche* Vorlage gilt, muss eindeutig
    beantwortbar sein. Bei zwei Erzeugungen ist sie es nicht: zwei Erzeugungen sind zwei
    Aufträge. Weitere Zeilen aus dem Lager sind erlaubt – das ist die **Montage**:

    ===================  =======  =====================================
    Maschine             Neu      das Produkt, fährt seine Vorlage
    Rahmen · Motor · …   Lager    die Komponenten, werden verbaut
    ===================  =======  =====================================
    """
    new_lines = [ln for ln in lines if ln.origin == NEU]
    if len(new_lines) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{new_lines[1].label}: ein Auftrag hat genau einen Erzeugungsprozess – "
                f"«Neu» steht schon bei {new_lines[0].label}. Für den zweiten Artikel "
                f"einen eigenen Auftrag anlegen."
            ),
        )


def _assert_no_self_consumption(lines: list[_Line], steps: list[dict[str, Any]]) -> None:
    """**Ein Auftrag verbaut nicht, was er selbst erzeugt.**

    Die einzige Prüfung, die eine Stückliste bei der Freigabe braucht. Sie trifft
    **Artikel**, nicht Zeilen – stünde derselbe Artikel als ``Neu`` und in der Stückliste
    eines Verbrauchsmoduls, zöge dieses Modul Stücke desselben Artikels aus dem Lager,
    während der Auftrag ihn gerade herstellt. Was daraus wird, ist nicht mehr entscheidbar.

    **Dass die Komponenten im Auftrag stehen müssten, wird ausdrücklich NICHT geprüft** –
    sie stehen dort nicht mehr. Gebunden wird beim Erreichen des Moduls
    (``domain/modules.Verbrauch``), also hat der Auftrag zur Freigabezeit gar keine Zeile
    dafür. Reicht der Bestand dann nicht, sagt es das Modul (``services/consumption``);
    das ist eine Frage der Laufzeit und keine der Freigabe.
    """
    named: list[int] = []
    for step in steps:
        named += [row["article"] for row in modules.lines_of(step.get("config"))]
    produced = {ln.article.object_id for ln in lines if ln.origin == NEU}
    clash = [n for n in dict.fromkeys(named) if n in produced]
    if clash:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Artikel {clash[0]} wird in diesem Auftrag erzeugt und steht zugleich in "
                f"der Stückliste eines Verbrauchsmoduls. Ein Auftrag kann nicht verbauen, "
                f"was er gerade herstellt."
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

    Es gibt höchstens eine ``Neu``-Zeile (``_assert_single_new``) – die Frage «welche von
    zwei Vorlagen gilt» kann es darum gar nicht geben. Daneben stehende ``Lager``-Zeilen
    laufen durch dieselbe Vorlage.
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


def pick_problem(unit: InstanceUnit, number: str) -> Optional[str]:
    """►►► **Darf ein Auftrag dieses Stück greifen?** ◄◄◄ ``None`` = ja.

    **Die eine Antwort, in einem Satz** – und sie nennt keinen Status, sondern fragt die
    Eigenschaft: ein **Endzustand** ist endgültig, also gibt es nichts mehr zu tun, also
    nimmt ihn kein Auftrag auf. Ein **gesperrtes** Stück dagegen ist nicht terminal, und
    das Greifen IST das Aufheben der Sperre – es bleibt wählbar, und genau das ist der
    Weg zurück (§5.2).

    Ein künftiger terminaler Zustand erbt das ohne eine Zeile Code.

    **Warum als Rückgabe und nicht als Wurf:** dieselbe Regel muss zweimal gestellt
    werden – die Freigabe bricht damit ab (409), der Entwurf meldet damit, was fehlt
    (``orders.validate_draft``). Zwei Formulierungen wären zwei Massstäbe, und der
    mildere stünde irgendwann an dem Knopf, der beim Klick scheitert.
    """
    if st.is_terminal(unit.status):
        return (
            f"Einzelinstanz {number} ist «{st.label(unit.status)}» – das ist ein "
            f"Endzustand. Sie kann in keinem Auftrag mehr vorkommen."
        )
    return None


def unpickable(db: Session, lines: list["_Line"]) -> list[str]:
    """Dieselbe Regel für den **Entwurf**: welche gewählten Stücke gehen nicht?

    Die zweite Form von ``pick_problem`` – sie sammelt, statt beim ersten Fund
    abzubrechen, weil ein Entwurf **alles** nennen soll, was ihm im Weg steht.
    Unbekannte oder doppelte Nummern meldet ``_resolve_units`` bereits selbst.
    """
    out: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        if ln.origin != LAGER:
            continue
        for unit, number in _resolve_units(db, [n for n, _ in ln.picks], seen=seen):
            problem = pick_problem(unit, number)
            if problem:
                out.append(problem)
    return out


def _resolve_units(db: Session, numbers: list[str], *, seen: set[str]) -> list[tuple[InstanceUnit, str]]:
    """Nummern → Einzelinstanzen. Unbekannt oder doppelt = harter Fehler, kein Filtern."""
    clean = [(raw or "").strip() for raw in numbers]
    found = find_units(db, clean)
    out: list[tuple[InstanceUnit, str]] = []
    for number in clean:
        if number in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Einzelinstanz {number} ist doppelt in der Definition.",
            )
        seen.add(number)
        unit = found.get(number)
        if unit is None or not unit.is_active:
            raise HTTPException(
                status_code=404, detail=f"Einzelinstanz {number} gibt es nicht.",
            )
        out.append((unit, number))
    return out


def _assert_may_leave(db: Session, membership: OrderUnit, number: str) -> None:
    """►►► Die markierte Stelle zur offenen Frage (Abweichungsauftrag §5) ◄◄◄

    **Darf das Stück den Modultyp verlassen, vor dem es gerade steht?** Die Antwort
    steht am **Modultyp** (``domain/modules.Module.units_may_leave``), nicht hier: eine
    globale Regel wäre für die reversible Datenerfassung zu streng und für ein Modul mit
    Aussenwirkung zu lasch.

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
    running = holders(db, list(held))

    stale: list[dict[str, Any]] = []
    for unit, number in pairs:
        was = stated.get(number)
        now = running.get(unit.id)
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


def _lock_picks(db: Session, lines: list[_Line],
                picked: dict[int, list[tuple[InstanceUnit, str]]]) -> None:
    """Die Freigabe sperrt, was sie übernimmt: **erst die Quell-Aufträge, dann die Stücke.**

    Dieselbe Reihenfolge wie beim Bestätigen (Auftrag vor Stück), sonst warteten zwei
    Vorgänge im Kreis aufeinander. Gesperrt werden die Aufträge, in denen die Stücke jetzt
    laufen, und die, aus denen der Mensch sie gewählt hat. Danach werden die Stücke neu
    gelesen (``populate_existing``): was zwischen Auswahl und Sperre passiert ist, sieht die
    Prüfung dahinter (``_assert_as_picked``).
    """
    ids = sorted({u.id for pairs in picked.values() for u, _ in pairs})
    if not ids:
        return
    stated = {oid for ln in lines for _, oid in ln.picks if oid}
    sources = {m.order_id for m in held_by(db, ids).values()}
    if stated:
        sources |= {int(i) for (i,) in
                    db.query(Order.id).filter(Order.object_id.in_(stated)).all()}
    lock_orders(db, sources)
    for part in _chunks(ids):
        (db.query(InstanceUnit).filter(InstanceUnit.id.in_(part))
         .order_by(InstanceUnit.id).with_for_update().populate_existing().all())


def _take_picks(db: Session, lines: list[_Line], *, lock: bool) -> None:
    """Die gewählten Stücke auflösen und prüfen: frei übernehmen oder **aus einem laufenden
    Auftrag** herüberholen.

    Beides führt durch dasselbe Start-Objekt (§4.1) – der Status eines Stücks sagt, ob es
    in EINEM Prozess ist, nicht in welchem. **Darf ein Auftrag dieses Stück greifen?**
    gilt für **jedes** Stück, nicht nur für freie.
    """
    seen: set[str] = set()
    picked = {ln.position: _resolve_units(db, [n for n, _ in ln.picks], seen=seen)
              for ln in lines if ln.origin == LAGER}
    if lock:
        _lock_picks(db, lines, picked)
    for ln in lines:
        if ln.origin != LAGER:
            continue
        pairs = picked[ln.position]
        held = held_by(db, [u.id for u, _ in pairs])
        _assert_as_picked(db, ln, pairs, held)
        for unit, number in pairs:
            problem = pick_problem(unit, number)
            if problem:
                raise HTTPException(status_code=409, detail=problem)
            source = held.get(unit.id)
            if source is not None:
                _assert_may_leave(db, source, number)
                ln.taken[unit.id] = source
        ln.units = [u for u, _ in pairs]


def _checked(db: Session, lines: list[dict[str, Any]], steps: list[dict[str, Any]],
             *, lock: bool = False) -> tuple[list[_Line], list[dict[str, Any]]]:
    """►►► **Teil 1 der Freigabe: alles prüfen, was ohne Nummer prüfbar ist.** ◄◄◄

    Die eine Prüfung für Freigabe **und** Entwurf (``orders.validate_draft``): was die
    Freigabe abweist, meldet der Entwurf mit demselben Satz. Zwei Massstäbe wären ein Knopf,
    der bereitsteht und beim Klick scheitert. ``lock`` nimmt nur die Freigabe – ein Entwurf
    prüft, er hält nichts fest.
    """
    resolved = resolve_lines(db, lines)
    effective = steps_for(db, resolved, steps)
    missing = assert_releasable(sum(ln.quantity for ln in resolved), effective)
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Auftrag ist noch nicht freigebbar – es fehlt: "
                   + ", ".join(missing) + ".",
        )
    for step in effective:
        st.assert_known(step["status_before"], field="Vorher-Status")
        st.assert_known(step["status_after"], field="Nachher-Status")
    chain.assert_closes(effective)
    _assert_no_self_consumption(resolved, effective)
    _take_picks(db, resolved, lock=lock)

    # Der Plan muss aufgehen, bevor er etwas kostet (§2, harte Invariante). Bei «Neu» rein
    # arithmetisch – die Serialisierung wird geprüft, ohne eine Nummer zu ziehen.
    planned: list[tuple[int, int, str]] = []
    for ln in resolved:
        if ln.origin == NEU:
            count, each = materialize.plan(ln.article.serialization, ln.quantity)
            planned.append((ln.quantity, count * each, ln.label))
        else:
            planned.append((ln.quantity, len(ln.units), ln.label))
    materialize.assert_quantity(planned, code=400)
    return resolved, effective


def release(
    db: Session,
    *,
    lines: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    actor_id: Optional[int],
) -> Order:
    """Freigeben = den Prozess starten. **Eine Transaktion**, feste Reihenfolge (§6.3).

    **Jede Prüfung liegt vor der ersten Objektnummer** (``_checked``). Eine Sequence ist
    absichtlich nicht transaktional, ein Rollback danach liesse eine Lücke; ein
    abgebrochener Freigabe-Versuch verbraucht darum keine Nummer.
    """
    resolved, effective = _checked(db, lines, steps, lock=True)
    order, rows = _write_definition(db, resolved, effective)

    # Neue Stücke erzeugen – die EINZIGE Stelle, an der das passiert – und das Ergebnis
    # gegen dieselbe Invariante halten wie den Plan.
    for ln in resolved:
        if ln.origin == NEU:
            ln.units = materialize.create_for_line(db, article=ln.article, quantity=ln.quantity)
    materialize.assert_quantity(
        [(ln.quantity, len(ln.units), ln.label) for ln in resolved], code=500,
    )
    # Übernahme: die Stücke verlassen ihren bisherigen Auftrag – **vor** dem Anlegen der
    # neuen Zeilen, der partielle Unique-Index prüft je Anweisung. Ein verbautes Stück
    # greifen IST der Ausbau: es liegt danach, wo sein Träger liegt.
    _hand_over(db, order=order, lines=resolved, actor_id=actor_id)
    places_svc.take_out(db, [u for ln in resolved if ln.origin == LAGER for u in ln.units])

    # Die Stücke passieren das Start-Objekt, jedes mit eigenem Log-Eintrag. Die
    # **Verbindung** entsteht hier und nirgends sonst: gekappt (``None``) heisst, der
    # Quell-Auftrag läuft mit weniger Stücken weiter.
    all_units = [u for ln in resolved for u in ln.units]
    membership_ids = _join(db, [
        {"order_id": order.id, "instance_unit_id": u.id,
         "return_to_order_id": (ln.taken[u.id].order_id
                                if (ln.returns and u.id in ln.taken) else None)}
        for ln in resolved for u in ln.units
    ])
    _pass(
        db, order=order, units=all_units, membership_ids=membership_ids,
        kind=KIND_START, step=None,
        status_after=st.START_AFTER, next_step_id=rows[0].id, actor_id=actor_id,
    )
    # Das erste Modul ist damit erreicht: hier wird die Stichprobe gezogen, über die
    # **Gesamtmenge** des Auftrags (§2 – vorher steht die Menge nicht fest).
    sampling.ensure(db, order=order, step=rows[0], actor_id=actor_id)
    # Und jedes «Zahlung»-Modul bekommt seinen Beleg – idempotent, ohne ein solches Modul
    # ein No-op.
    voucher_svc.instantiate_for_order(db, order, actor_id=actor_id)
    return order


def _write_definition(db: Session, lines: list[_Line],
                      steps: list[dict[str, Any]]) -> tuple[Order, list[ProcessStep]]:
    """Ab hier werden Nummern vergeben: der Auftrag, seine Zeilen, seine Module."""
    from .objects import next_object_id

    object_id = next_object_id(db, "order")
    # Der Name entsteht im selben Zug wie die Nummer – vorher gibt es keine.
    order = Order(object_id=object_id, name=f"Auftrag {object_id}")
    db.add(order)
    db.flush()
    for ln in lines:
        db.add(OrderLine(order_id=order.id, position=ln.position, article_id=ln.article.id,
                         quantity=ln.quantity, origin=ln.origin))
    rows = [
        ProcessStep(
            order_id=order.id, position=position, module_type=step["module_type"],
            status_before=step["status_before"], status_after=step["status_after"],
            config=step.get("config"), source_article_id=step.get("source_article_id"),
            source_version=step.get("source_version"),
        )
        for position, step in enumerate(steps, start=1)
    ]
    db.add_all(rows)
    db.flush()
    return order, rows


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
    db.flush()

    # **Die Quell-Aufträge sehen ihre Stelle neu.** Nimmt eine Abweichung das letzte
    # gezogene Stück eines Moduls mit, ist dessen Stichprobe damit erledigt – und was dort
    # noch steht, ist der ungezogene Rest. Er wartete sonst auf einen Scan, den niemand
    # verlangt: der Auftrag stünde still, ohne dass jemand etwas tun könnte.
    for src_id, at in {(m.order_id, m.current_step_id) for m, _ in taken}:
        if at is None:
            continue
        src = db.query(Order).filter(Order.id == src_id).first()
        step = db.query(ProcessStep).filter(ProcessStep.id == at).first()
        if src is not None and step is not None:
            _run_through(db, order=src, step=step, actor_id=actor_id)
