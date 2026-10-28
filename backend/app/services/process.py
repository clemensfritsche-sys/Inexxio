"""**Der Prozess: Freigabe, Schritt bestätigen, Zustand ableiten.**

Die eine Stelle, an der Einzelinstanzen ihren Status wechseln. Jeder Wechsel schreibt
im selben Atemzug einen Eintrag in den Ereignis-Log (Ebene 3) und zieht die Projektionen
nach (Ebene 2) — es gibt keinen zweiten Schreibweg, und darum können die beiden nicht
auseinanderlaufen.

Gelesen wird PROCESS_CORE.md; hier steht nur, was daraus folgt.
"""

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import chain, modules, statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent,
    ProcessStep,
)
from ..models.order_line import LAGER, NEU, ORIGINS
from ..models.process_event import (
    KIND_CAPTURE, KIND_END, KIND_HANDOVER, KIND_RETURN, KIND_START, KIND_STEP,
)
from . import (
    article_process, articles as articles_svc, capture as capture_svc,
    consumption as consumption_svc, materialize,
    voucher as voucher_svc,
    places as places_svc, sampling,
)
from .instances import find_units, number_of, unit_numbers

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

def _assert_not_terminal(db: Session, units: list[InstanceUnit], status_after: str) -> None:
    """►►► **Ein Endzustand wird nicht überschrieben.** ◄◄◄

    Die Prüfung sitzt hier, weil hier **jeder** Statuswechsel durchläuft (§4.1): Start,
    Modul, Ende – es gibt keinen zweiten Schreibweg, und darum gibt es auch keinen Weg an
    ihr vorbei. Ein neues Modul erbt sie, ohne von ihr zu wissen; es fragt gar nicht, ob
    es darf, ihm wird gesagt, dass es nicht darf.

    **An der falschen Stelle wäre sie eine Hoffnung.** Sie am Modul zu prüfen hiesse: an
    jedem Modul, für immer, und beim ersten vergessenen ist der Endzustand weg. Sie in der
    Freigabe zu prüfen deckt nur den Eintritt ab – ``release`` tut das ohnehin
    (``is_selectable``), aber nur für **freie** Stücke; ein Stück, das noch in einem
    Auftrag liegt, kommt dort gar nicht an dieser Prüfung vorbei.

    **Und darunter liegt der Trigger** (``statuses.terminal_guard_sql``): dieselbe Regel
    als Eigenschaft der Tabelle. Diese Stelle hier gibt es nicht, weil die Datenbank
    unsicher wäre, sondern damit der Fehler einen **Satz** hat statt einer rohen
    Datenbank-Meldung – und damit er den Vorgang abbricht, bevor irgendetwas geschrieben
    ist.
    """
    stuck = [u for u in units if st.is_terminal(u.status)]
    if not stuck:
        return
    first = stuck[0]
    raise HTTPException(
        status_code=409,
        detail=(
            f"Einzelinstanz {number_of(db, first)} ist «{st.label(first.status)}» – das ist "
            f"ein Endzustand. Er wird nicht überschrieben"
            + (f" (versucht: «{st.label(status_after)}»)" if status_after else "")
            + (f"; betroffen sind {len(stuck)} Stücke" if len(stuck) > 1 else "")
            + ". Was passiert ist, ist passiert."
        ),
    )


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
    _assert_not_terminal(db, units, status_after)

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

    # ►► **Jedes Stück behält seinen Ort – ausser es ist endgültig weg.** ◄◄
    #
    # Ein verschrottetes Stück gibt es nicht mehr; sein alter Halter wäre eine Behauptung
    # über etwas, das dort nicht ist. Alles andere liegt irgendwo: gesperrt im Sperrlager,
    # **verkauft** noch in Halle 2 bis zur Abholung. Ein verbautes Stück bekommt im selben
    # Zug seinen Träger als Ort (der Verbrauch setzt ihn).
    #
    # Die Regel hängt am **Status** und steht an der EINEN Stelle, an der ein Status
    # geschrieben wird – jedes künftige Modul erbt sie, ohne eine Zeile dafür.
    if st.is_terminal(status_after):
        places_svc.forget(db, units)
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
    """**Höchstens EINE «Neu»-Zeile** (Testnotiz #693, präzisiert für die Montage).

    Ein Erzeugungsauftrag fährt die **Vorlage des Artikels**, als Kopie mit
    Versionsstempel (§2.1). Der Stempel sagt «diese Stücke sind genau so entstanden, wie
    Artikel X es beschreibt» – und die Frage, *welche* Vorlage gilt, muss eindeutig
    beantwortbar sein. Bei zwei Erzeugungen ist sie es nicht: zwei Erzeugungen sind zwei
    Aufträge.

    **Die Regel hiess einmal «Neu steht für sich allein»** – und war damit einen Tick zu
    breit. Sie verbot nicht nur die zweite Vorlage, sondern **jede** weitere Zeile, also
    ausgerechnet die Auftragsform, die eine **Montage** ist:

    ===================  =======  =====================================
    Maschine             Neu      das Produkt, fährt seine Vorlage
    Rahmen · Motor · …   Lager    die Komponenten, werden verbaut
    ===================  =======  =====================================

    Der ursprüngliche Grund bleibt dabei vollständig gewahrt: es gibt weiterhin genau
    **eine** Vorlage, und der Stempel gilt für die Stücke, die sie erzeugt hat.
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
    out: dict[int, int] = {}
    for part in _chunks(list(unit_ids)):
        for uid, oid in (
            db.query(OrderUnit.instance_unit_id, Order.object_id)
            .join(Order, Order.id == OrderUnit.order_id)
            .filter(OrderUnit.instance_unit_id.in_(part), OrderUnit.released_at.is_(None))
            .all()
        ):
            out[int(uid)] = int(oid)
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


def lock_orders(db: Session, order_ids: Iterable[int]) -> None:
    """►►► **Aufträge sperren, bevor an ihnen geschrieben wird** – in fester Reihenfolge. ◄◄◄

    Jeder Schreibweg an einem laufenden Auftrag (Bestätigen, die Stücke durch ein
    Zahlungsmodul ziehen, die Übernahme aus ihm, die Rückkehr in ihn) nimmt zuerst diese
    Zeilensperre. Damit lesen zwei gleichzeitige Vorgänge am selben Auftrag nie denselben
    Stand: der zweite wartet, bis der erste festgeschrieben ist, und sieht dann dessen
    Ergebnis – die Stichprobe wird einmal gezogen, ein Stück einmal bewegt. Sortiert nach
    ``id``, damit zwei Vorgänge, die mehrere Aufträge sperren, sich nicht gegenseitig
    blockieren. Innerhalb derselben Transaktion ist eine zweite Sperre derselben Zeile frei.
    """
    ids = sorted({int(i) for i in order_ids})
    if ids:
        db.execute(select(Order.id).where(Order.id.in_(ids)).order_by(Order.id)
                   .with_for_update())


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


def _join(db: Session, rows: list[dict[str, Any]]) -> list[int]:
    """Die Zugehörigkeiten anlegen – **ein Stück in genau einem Auftrag** (§3).

    Die Sperren davor schliessen den Wettlauf aus; bleibt doch ein Verstoss gegen den
    partiellen Unique-Index, ist das ein 409 mit der Nummer des Stücks, nicht eine rohe
    Datenbankmeldung. Der Savepoint hält die Transaktion dafür lesbar.
    """
    try:
        with db.begin_nested():
            db.execute(insert(OrderUnit), rows)
    except IntegrityError as exc:
        found = re.search(r"\(instance_unit_id\)=\((\d+)\)", str(exc.orig))
        unit = db.get(InstanceUnit, int(found.group(1))) if found else None
        name = f"Einzelinstanz {number_of(db, unit)}" if unit else "Eine Einzelinstanz"
        raise HTTPException(
            status_code=409,
            detail=(f"{name} läuft inzwischen in einem anderen Auftrag – die Auswahl ist "
                    f"veraltet. Bitte prüfen und erneut freigeben."),
        ) from None
    return [int(i) for (i,) in db.query(OrderUnit.id).filter(
        OrderUnit.order_id == rows[0]["order_id"],
        OrderUnit.instance_unit_id.in_([r["instance_unit_id"] for r in rows]),
        OrderUnit.released_at.is_(None),
    ).all()]


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


def _enter_at_step(db: Session, *, order: Order, step: ProcessStep,
                   units: list[InstanceUnit], actor_id: Optional[int]) -> list[int]:
    """►►► **Der zweite Eintrittspunkt: ein Stück tritt an einem MODUL in den Auftrag.** ◄◄◄

    Für ein Modul, das sich sein Material erst holt, wenn es dran ist (``release`` kennt
    nur das Start-Objekt).

    **Verallgemeinert ist der Punkt, nicht der Mechanismus.** Es ist derselbe Eintritt –
    dieselbe Zeile in ``order_units``, dasselbe ``start``-Ereignis, derselbe Übergang auf
    ``Im Prozess``, dieselbe Exklusivität (der partielle Unique-Index greift ab jetzt).
    Nur die Antwort auf «und wo steht es dann?» ist eine andere: nicht vor dem ersten
    Modul, sondern vor **diesem**.

    Zwei Dinge stehen bewusst nicht hier:

    * **Keine Rückführung.** Wer an einem Modul eintritt, kam aus dem freien Bestand und
      hat keinen Auftrag, in den er zurückkönnte (``return_to_order_id`` bleibt ``NULL``).
    * **Kein Schutz gegen einen laufenden Halter.** Den gibt es schon: die Auswahl der
      Stücke passiert eine Ebene höher und nimmt ausschliesslich freie
      (``services/consumption``); wäre eines doch gebunden, wiese es der Unique-Index ab.

    Der ``start``-Eintrag trägt hier – anders als am Start-Objekt – die Modul-``id``.
    Genau daran unterscheidet der Graph die beiden (``flow._tally``): das Start-Objekt hat
    passiert, wer oben hereinkam; wer an einem Modul eintritt, hat es nie gesehen.
    """
    if not units:
        return []
    ids = _join(db, [{"order_id": order.id, "instance_unit_id": u.id,
                      "return_to_order_id": None} for u in units])
    _pass(
        db, order=order, units=units, membership_ids=ids,
        kind=KIND_START, step=step,
        status_after=st.START_AFTER, next_step_id=step.id, actor_id=actor_id,
    )
    return ids


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
    # noch steht, ist der ungezogene Rest. Er wartete sonst auf einen Scan, den es nach
    # #714 nicht mehr gibt: der Auftrag stünde still, ohne dass jemand etwas tun könnte.
    for src_id, at in {(m.order_id, m.current_step_id) for m, _ in taken}:
        if at is None:
            continue
        src = db.query(Order).filter(Order.id == src_id).first()
        step = db.query(ProcessStep).filter(ProcessStep.id == at).first()
        if src is not None and step is not None:
            _run_through(db, order=src, step=step, actor_id=actor_id)


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


def step_of(db: Session, order: Order, step_id: int) -> ProcessStep:
    """Das Modul ``step_id`` **dieses** Auftrags – sonst 404. Die eine Nachschlage-Stelle."""
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    return step


def confirm_step(
    db: Session, *, order: Order, step_id: int, values: dict[str, dict[str, Any]],
    actor_id: Optional[int],
    instance_object_id: Optional[int] = None,
    verification: Optional[str] = None,
    sources: Optional[list[int]] = None,
    place: Optional[int] = None,
    auto: bool = False,
) -> dict[str, Any]:
    """«Bestätigen» — der eine Mechanismus, den jedes Modul auslöst.

    Prüft die Verifikation, prüft den Vorher-Status, lässt das Modul festhalten was es
    festhält, setzt den Nachher-Status, loggt, rückt vor. Ist der Schritt der letzte,
    passiert das Stück im selben Zug das **Ende-Objekt** und wird frei.

    **Ein Vorgang ist EINE Instanz** (§3): der Scan verifiziert sie. **Die Erfassung
    dagegen gilt der Einzelinstanz** – ``values`` trägt einen eigenen Wertesatz je
    gezogenem Stück, geschlüsselt nach seiner Nummer.

    **Erfassung und Verbrauch liegen VOR dem Statuswechsel**: fehlt ein Pflichtpunkt oder
    reicht der Bestand nicht, ist das ein Fehler mit Namen – und es hat sich nichts bewegt.
    ``sources`` sind die Instanzen, aus denen verbraucht werden soll (leer = der ganze
    freie Bestand, FIFO).

    **«Nicht bestanden» rückt NICHT vor** (§4): die Feststellung ist geloggt, die Stücke
    bleiben stehen, und was daraus folgt, entscheidet ein Mensch.

    **Der Auftrag ist gesperrt, solange das läuft** (``lock_orders``): zwei gleichzeitige
    Vorgänge am selben Auftrag laufen nacheinander.
    """
    lock_orders(db, [order.id])
    step = step_of(db, order, step_id)
    waiting = _ready_at(db, order=order, step=step, auto=auto,
                        instance_object_id=instance_object_id, verification=verification)
    units = [u for _, u in waiting]
    result = _record(db, order=order, step=step, units=units, values=values,
                     verification=verification, actor_id=actor_id)
    # **Nicht bestanden ⇒ nichts rückt vor.** Auch die nicht gezogenen Stücke dieser
    # Instanz bleiben stehen: die Stichprobe ist nicht mehr repräsentativ, der ungeprüfte
    # Rest verdächtig (§4.1).
    if result == "failed":
        db.flush()
        return {"moved": 0, "held": len(units), "result": result}
    _advance(db, order=order, step=step, waiting=waiting, verification=verification,
             sources=sources, place=place, actor_id=actor_id)
    db.flush()
    # **Was hier nicht gezogen wurde, läuft jetzt mit** (§9.3) – siehe ``_run_through``.
    _run_through(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    # ►► **Ein Zahlungsmodul weiter hinten lässt durch, was es darf.** ◄◄ Nur beim Klick
    # eines Menschen – ``advance_payments`` ruft hier selbst mit ``auto``.
    if not auto:
        advance_payments(db, order=order, actor_id=actor_id)
    return {"moved": len(units), "held": 0, "result": result}


def _ready_at(db: Session, *, order: Order, step: ProcessStep, auto: bool,
              instance_object_id: Optional[int],
              verification: Optional[str]) -> list[tuple[OrderUnit, InstanceUnit]]:
    """**Darf hier jetzt bestätigt werden – und woran?** Die Stücke, die davorstehen."""
    current = order_status(db, order)
    if current != st.IM_PROZESS:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Auftrag ist «{st.label(current)}» – "
                    f"es gibt nichts mehr zu bestätigen."),
        )
    # **Ein Zahlungsmodul bestätigt niemand von Hand** – die Stücke ziehen von selbst
    # weiter, sobald sie dürfen (``advance_payments`` ruft hier mit ``auto``).
    voucher_svc.assert_completable(db, step=step, auto=auto)
    instance = _verified_instance(
        db, order=order, step=step,
        instance_object_id=instance_object_id, verification=verification,
    )
    # ►► **Die Sperre der Rückführung — hier und nur hier.** ◄◄ Am EINEN
    # Ausführungs-Mechanismus, den jedes Modul auslöst; ein neuer Modultyp erbt sie.
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
    for _, unit in waiting:
        if unit.status != step.status_before:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Einzelinstanz {number_of(db, unit)} steht auf "
                    f"«{st.label(unit.status)}», «{modules.label(step.module_type)}» erwartet "
                    f"«{st.label(step.status_before)}»."
                ),
            )
    return waiting


def _record(db: Session, *, order: Order, step: ProcessStep, units: list[InstanceUnit],
            values: dict[str, dict[str, Any]], verification: Optional[str],
            actor_id: Optional[int]) -> Optional[str]:
    """**Festhalten, was das Modul festhält** – je gezogener Einzelinstanz ein Wertesatz.

    Gezogen ist, was die Stichprobe beim Erreichen gezogen hat (``sampling.ensure`` ist
    idempotent und steht hier als Netz). Die **nicht** gezogenen laufen ohne Erfassung
    durch; sichtbar ist das, weil sie keinen ``capture``-Eintrag haben. **Eine
    durchgefallene Einzelinstanz hält die ganze Instanz an** (§4.1): das Urteil je Stück
    steht in seiner Zeile, zurück kommt, ob eines fiel.
    """
    sampling.ensure(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    drawn_ids = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    drawn = [u for u in units if u.id in drawn_ids]
    by_unit = _captures_for(db, step=step, drawn=drawn, values=values)
    captures = capture_svc.record_for_step(
        db, order=order, step=step, units=drawn, captures=by_unit, actor_id=actor_id,
    )
    if captures:
        db.execute(insert(ProcessEvent), [
            {
                "order_id": order.id, "step_id": step.id, "instance_unit_id": u.id,
                "kind": KIND_CAPTURE,
                # Erfassen ist keine Zustandsänderung – gemessen wird, was da ist.
                "status_before": u.status, "status_after": u.status,
                # **Das Urteil dieses Stücks**, nicht das der Instanz (§9.5).
                "payload": {"capture_id": captures[u.id].id,
                            "result": captures[u.id].result,
                            "verification": verification},
                "actor_id": actor_id,
            }
            for u in drawn
        ])
    results = [c.result for c in captures.values()]
    return "failed" if "failed" in results else next(iter(results), None)


def _advance(db: Session, *, order: Order, step: ProcessStep,
             waiting: list[tuple[OrderUnit, InstanceUnit]], verification: Optional[str],
             sources: Optional[list[int]], place: Optional[int],
             actor_id: Optional[int]) -> None:
    """**Das Modul wirkt, die Stücke passieren es.** Derselbe Weg für jeden Modultyp.

    Erst der **Ort** (``places.apply_for_step``), dann der **Verbrauch**
    (``consumption.plan``) – beide prüfen, bevor sich ein Status ändert, und beide geben
    für ein Modul, das nichts bewegt bzw. nichts verbaut, nichts zurück. Was dabei passiert
    ist (Herkunft, Ziel, Verifikation), reist als Payload in den Log (§7.2).

    An einem **Ausgang** (``Module.terminal``) verlässt alles den Auftrag mit dem
    Ausgangszustand und passiert das Ende-Objekt **nicht** – dort hängt die Rückführung,
    und ein ausgesondertes Stück kehrt nirgends zurück. Sonst rückt es zum nächsten Modul
    vor (dort wird jetzt gezogen) oder durch das Ende-Objekt hinaus.
    """
    module = modules.get(step.module_type)
    units = [u for _, u in waiting]
    moved = places_svc.apply_for_step(db, step=step, units=units, target=place)
    marks = {u.id: {"verification": verification, **moved.get(u.id, {})} for u in units}
    built = consumption_svc.plan(db, step=step, products=units, sources=sources)
    if built:
        _build_in(db, order=order, step=step, products=units, built=built,
                  verification=verification, actor_id=actor_id)
    following = None if module.terminal else _following(db, order, step)
    _pass(
        db, order=order, units=units, membership_ids=[m.id for m, _ in waiting],
        kind=KIND_STEP, step=step,
        status_after=(module.exit_status_for(step.config) if module.terminal
                      else step.status_after),
        next_step_id=following.id if following else None,
        actor_id=actor_id, payloads=marks,
    )
    if module.terminal:
        return
    if following is None:
        _finish(db, order=order, rows=waiting, actor_id=actor_id)
    else:
        sampling.ensure(db, order=order, step=following, actor_id=actor_id)


def _build_in(db: Session, *, order: Order, step: ProcessStep, products: list[InstanceUnit],
              built: dict[int, list[InstanceUnit]], verification: Optional[str],
              actor_id: Optional[int]) -> None:
    """**Verbauen**: die Komponenten treten am Modul ein und gehen im selben Zug hinaus.

    Die beiden Übergänge des Statuswegs ``Freigegeben`` → ``Im Prozess`` → ``Verbaut``
    gehen beide durch ``_pass``, also stehen beide im Log. **Worin** steht im Payload
    (``into``) – das ist die ganze Genealogie (§3). Danach ist der **Träger** der neue Ort
    (``places.place_in``): dieses Stück, nicht seine Instanz. Der Zeiger sagt, wo es jetzt
    liegt, und wird beim Ausbau geräumt (``places.take_out``); die Genealogie im Log
    bleibt (§9.6).
    """
    taken = [c for group in built.values() for c in group]
    ids = _enter_at_step(db, order=order, step=step, units=taken, actor_id=actor_id)
    _pass(
        db, order=order, units=taken, membership_ids=ids,
        kind=KIND_STEP, step=step,
        status_after=modules.get(step.module_type).exit_status_for(step.config) or st.VERBAUT,
        next_step_id=None, actor_id=actor_id,
        payloads=consumption_svc.payloads(built, verification=verification),
    )
    by_product = {p.id: p for p in products}
    for product_id, components in built.items():
        places_svc.place_in(db, units=components, carrier=by_product[product_id])


def advance_payments(db: Session, *, order: Order, actor_id: Optional[int]) -> int:
    """►►► **Die Stücke ziehen durch ein Zahlungsmodul – von selbst.** ◄◄◄

    Es gibt dort keinen Knopf: mit der Zusage (bei einer Vorauszahlung mit dem Geld) dürfen
    die Stücke weiter (``voucher.passable``). Gefragt wird nach **jedem** Zahlungsmodul
    dieses Auftrags, vor dem Stücke stehen und das nicht auf eine Rückführung wartet.
    Derselbe Weg wie jeder andere (``confirm_step``), also dieselbe Spur im Log.

    Endlich: jeder Durchgang bewegt Stücke nach hinten, und ein Prozess ist azyklisch.
    Gibt zurück, wie viele Stücke weitergezogen sind.
    """
    lock_orders(db, [order.id])
    # **Erkannt daran, dass es einen Beleg gibt** – nie am Modultyp. Einmal gelesen: die
    # Belege entstehen mit der Freigabe.
    paying = [s for s in steps_of(db, order) if voucher_svc.of_step(db, s.id) is not None]
    moved = 0
    for _ in range(64):
        if not paying or order_status(db, order) != st.IM_PROZESS:
            return moved
        blocked = pending_returns(db, order)
        ready = next((s for s in paying
                      if s.id not in blocked and _units_at(db, order, s.id)
                      and voucher_svc.pass_problem(db, step=s) is None), None)
        if ready is None:
            return moved
        moved += confirm_step(db, order=order, step_id=ready.id, values={},
                              actor_id=actor_id, verification=VERIFY_MANUAL,
                              auto=True)["moved"]
    return moved


def _following(db: Session, order: Order, step: ProcessStep) -> Optional[ProcessStep]:
    """Das Modul **nach** diesem – oder ``None``, wenn danach das Ende kommt."""
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.position > step.position)
        .order_by(ProcessStep.position)
        .first()
    )


def _sample_cleared(db: Session, *, order: Order, step: ProcessStep) -> bool:
    """Ist die Stichprobe **dieses Moduls** durch — und bestanden?

    Zwei Bedingungen, beide aus §4.1/§9.3, keine davon typabhängig:

    1. **Jedes gezogene Stück ist hier erfasst.** Solange eines aussteht, ist die
       Stichprobe nicht durch – auch wenn es noch bei einem Modul davor steht.
    2. **Keines ist durchgefallen.** Ein negatives Urteil hält an, und zwar alles: die
       Stichprobe ist damit nicht mehr repräsentativ, der ungeprüfte Rest verdächtig
       (ISO 2859-1). Ihn ausgerechnet dann durchlaufen zu lassen wäre das stille
       Weiterlaufen, das §4.5 verhindert.

    **Ein Modul ohne Erfassungspunkte ist damit nie «durch»** – es erfasst nichts, also
    hat kein gezogenes Stück eine Erfassung. Genau richtig: beim Aussondern **ist** der
    Scan die Bestätigung, und die kann niemand einsparen. Das steht hier als Folge, nicht
    als Abfrage nach dem Modultyp.

    **Gelesen wird die Ziehung, nicht die Gegenwart** (``sampling.drawn_ids``): ein
    gezogenes Stück, das erfasst wurde und weitergezogen ist, hält keine offene
    Zugehörigkeit mehr. Wer nur die aktuelle Liste fragt, hielte die Stichprobe für leer –
    und liesse den Rest gerade dann durchlaufen, wenn noch nichts erfasst ist.

    **Ein Stück, das den Auftrag verlassen hat, hält nichts mehr auf.** Nimmt eine
    Abweichung den Durchfaller mit, kann er hier nie mehr erfasst werden; auf ihn zu
    warten wäre eine Sackgasse ohne Ausgang.
    """
    drawn = sampling.drawn_ids(db, order=order, step=step)
    if not drawn:
        return False
    here = {
        int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
            OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all()
    }
    latest = _latest_captures(db, order, step, list(drawn))
    for uid in drawn:
        capture = latest.get(uid)
        if capture is None:
            if uid in here:
                return False                       # steht hier noch aus
            continue                               # weg – kann hier nicht mehr erfasst werden
        if capture.result == "failed" and uid in here:
            return False                           # hält an, solange es hier steht (§4.1)
    return True


def _run_through(db: Session, *, order: Order, step: Optional[ProcessStep],
                 actor_id: Optional[int]) -> None:
    """►►► **Wer hier nicht gezogen wurde, wird hier auch nicht gescannt.** ◄◄◄

    Die Zahl der Scans folgt der Stichprobe, nicht umgekehrt (Testnotiz #714):

    ==========================  ==================================================
    **Zahl der Erfassungen**    Einzelinstanzen in der Stichprobe
    **Zahl der Scans**          **Instanzen**, zu denen diese gehören
    ==========================  ==================================================

    Vorher stand die Reihenfolge auf dem Kopf: **jede** wartende Instanz wurde zum Scan
    angeboten, und erst danach entschied die Ziehung, ob es dort etwas zu erfassen gab.
    Bei zwei Instanzen und 50 % hiess das zwei Scans für eine Erfassung – der zweite
    bestätigte nichts, er war nur der Weg, das Stück weiterzubewegen.

    **Bewegt wird es jetzt hier**, und zwar erst, wenn die Stichprobe dieses Moduls durch
    und bestanden ist (``_sample_cleared``). Nicht schon bei der Ankunft: fällt die
    Stichprobe durch, ist der ungeprüfte Rest verdächtig und darf den Betrieb nicht
    längst verlassen haben.

    Danach ist, was hier noch steht, genau der ungezogene Rest – ein gezogenes Stück wäre
    entweder erfasst (und vorgerückt) oder durchgefallen (und dann wäre nichts «durch»).
    Es passiert das Modul regulär, nur ohne Erfassung; im Log steht das als
    ``sampled: False``, also **sichtbar** statt stillschweigend (§9.3).

    Und es **kaskadiert**: am nächsten Modul kann dieselbe Instanz wieder ausserhalb der
    Ziehung liegen. Die Schleife merkt sich die besuchten Module – ein Prozess ist endlich
    und azyklisch, aber ein Wächter kostet hier nichts.
    """
    seen: set[int] = set()
    while step is not None and step.id not in seen:
        seen.add(step.id)
        # **Ein terminales Modul wird nie durchlaufen.** Es ist ein Ausgang (§4.6): was
        # dort passiert, verlässt den Auftrag endgültig, und das bestätigt ein Mensch.
        if modules.get(step.module_type).terminal:
            return
        if not _sample_cleared(db, order=order, step=step):
            return
        here = _units_at(db, order, step.id)
        if not here:
            return
        # **Nur das Ungezogene.** Ein gezogenes Stück, das noch hier steht, ist eine
        # andere Sache – es wartet, weil ein Geschwister durchgefallen ist, und es
        # weiterzubewegen wäre eine Entscheidung, die niemand getroffen hat.
        drawn = sampling.drawn_at(db, order=order, step=step,
                                  unit_ids=[u.id for _, u in here])
        waiting = [(m, u) for m, u in here if u.id not in drawn]
        if not waiting:
            return
        units = [u for _, u in waiting]
        following = _following(db, order, step)
        _pass(
            db, order=order, units=units, membership_ids=[m.id for m, _ in waiting],
            kind=KIND_STEP, step=step, status_after=step.status_after,
            next_step_id=following.id if following else None, actor_id=actor_id,
            payloads={u.id: {"sampled": False} for u in units},
        )
        if following is None:
            _finish(db, order=order, rows=waiting, actor_id=actor_id)
            db.flush()
            return
        sampling.ensure(db, order=order, step=following, actor_id=actor_id)
        db.flush()
        step = following


def _finish(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
            actor_id: Optional[int]) -> None:
    """Das Ende-Objekt. **Es setzt den Endzustand — es sei denn, das Stück geht weiter.**

    Das ist eine Regel, keine Fallunterscheidung: das Ende-Objekt reicht das Stück an
    den weiter, der als Nächstes kommt. Kommt niemand, wird es frei (§4.2) – oder
    **Verkauft**, wenn es einer anderen Partei gehört. Kommt der Auftrag, aus dem es
    geliehen war, bleibt es **Im Prozess** – es ist ja in einem.

    Die Stücke bewegen sich dabei in **Gruppen mit gleichem Ziel**, nicht einzeln: ein
    Auftrag kann geliehene und eigene Stücke gleichzeitig ans Ende bringen.
    """
    back = [(m, u) for m, u in rows if m.return_to_order_id]
    stay = [(m, u) for m, u in rows if not m.return_to_order_id]
    # ►►► **Was einer anderen Partei gehört, wird «Verkauft», nicht frei.** ◄◄◄ Wem es
    # gehört, sagt das jüngste nicht stornierte Zahlungsmodul, das es passiert hat
    # (``voucher.sold_units``) – keine gespeicherte Kopie, also wirkt ein Storno von selbst.
    # «Verkauft» ist Historie wie «Verbaut»: kein Bestand, kein FIFO, greifen nur als
    # Abweichung.
    sold = voucher_svc.sold_units(db, [u.id for _, u in stay])
    kept = [(m, u) for m, u in stay if u.id not in sold]
    gone = [(m, u) for m, u in stay if u.id in sold]

    for group, status_after in ((kept, st.DEFAULT_END_STATUS), (gone, st.VERKAUFT),
                                (back, st.IM_PROZESS)):
        if not group:
            continue
        _pass(
            db, order=order,
            units=[u for _, u in group], membership_ids=[m.id for m, _ in group],
            kind=KIND_END, step=None,
            status_after=status_after, next_step_id=None, actor_id=actor_id,
        )
    if not back:
        return
    # ►► **Zurück heisst: dort weiter, wo es ausgeschert ist.** ◄◄ Steht es vor einem Modul,
    # dessen Stichprobe inzwischen erledigt ist, oder vor einem zugesagten Zahlungsmodul,
    # wartete es sonst auf einen Vorgang, den niemand mehr verlangt.
    for home_id, at in _return_home(db, order=order, rows=back, actor_id=actor_id):
        home = db.get(Order, home_id)
        _run_through(db, order=home, step=db.get(ProcessStep, at), actor_id=actor_id)
        db.flush()
        advance_payments(db, order=home, actor_id=actor_id)


def _return_home(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
                 actor_id: Optional[int]) -> list[tuple[int, int]]:
    """Geliehene Stücke kehren an **genau die Stelle** zurück, an der sie ausgeschert sind.

    Die Stelle steht bereits da: die Zeile des Quell-Auftrags wurde beim Ausscheren
    geschlossen, ihr ``current_step_id`` aber nicht angetastet. Sie wieder zu öffnen
    **ist** die Rückführung – es gibt nichts nachzuschlagen und nichts zu berechnen.

    Möglich ist das erst hier, weil die Zeile dieses Auftrags eine Anweisung vorher
    geschlossen wurde: der partielle Unique-Index lässt genau eine offene Zugehörigkeit
    je Stück zu, und er prüft je Anweisung. Die Heimat-Aufträge sind gesperrt, bevor in
    sie geschrieben wird; zurück kommen ihre Rückkehrpunkte ``(Auftrag, Modul)``.
    """
    lock_orders(db, {m.return_to_order_id for m, _ in rows})
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
                    f"Einzelinstanz {number_of(db, u)} sollte in Auftrag "
                    f"{_order_number(db, m.return_to_order_id)} zurückkehren, findet dort "
                    f"aber keine offene Stelle – der Datenbestand ist kaputt."
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
    return sorted({(e["order_id"], e["step_id"]) for e in events})


# ---------------------------------------------------------------------------
# Ableitungen (Ebene 2 lesen)
# ---------------------------------------------------------------------------

def _captures_for(
    db: Session, *, step: ProcessStep, drawn: list[InstanceUnit],
    values: dict[str, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Nummern → Stück-ids, und die Deckung wird **verlangt**, nicht angenommen.

    Der Aufrufer schickt einen Wertesatz je Einzelinstanz, geschlüsselt nach ihrer
    **Nummer** – die sichtbare Identität, dieselbe, die auf dem Bildschirm steht. Interne
    ids kommen an der Oberfläche nicht vor.

    Geprüft wird in beide Richtungen, und beide Male ist es dieselbe Aussage: **erfasst
    wird, was gezogen wurde.**

    * Ein Satz für ein Stück, das **nicht gezogen** ist, wäre ein Nachweis über etwas,
      das an diesem Modul nie geprüft werden sollte.
    * Ein **fehlender** Satz wäre eine Lücke, die hinterher aussieht wie «durchgelaufen,
      nichts gemessen» – dabei war die Messung verlangt.

    Ohne Erfassungspunkte gibt es nichts zu decken (Aussondern: der Scan ist die
    Bestätigung); dann ist ein leerer Satz nicht nur erlaubt, sondern der einzige
    richtige.
    """
    points = capture_svc.points_of(step)
    if not points:
        if values:
            raise HTTPException(
                status_code=400,
                detail=(f"«{modules.label(step.module_type)}» erfasst nichts – "
                        f"hier ist kein Wert festzuhalten."),
            )
        return {}

    numbers = unit_numbers(db, drawn)
    by_number = {numbers[u.id]: u for u in drawn}
    unknown = sorted(set(values) - set(by_number))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(f"Für {', '.join(unknown)} ist hier nichts zu erfassen – "
                    f"diese Einzelinstanzen sind nicht gezogen."),
        )
    fehlend = sorted(n for n in by_number if n not in values)
    if fehlend:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{len(fehlend)} von {len(by_number)} Einzelinstanzen sind noch nicht "
                f"erfasst: {', '.join(fehlend[:5])}"
                + (" …" if len(fehlend) > 5 else "")
                + ". Erfasst wird je Stück, nicht je Scan."
            ),
        )
    return {by_number[n].id: v for n, v in values.items()}


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


def units_before(db: Session, order: Order, step: ProcessStep) -> list[InstanceUnit]:
    """**Was steht vor diesem Modul?** — die eine öffentliche Antwort.

    Gebraucht von jedem, der über das rechnet, was ankommt: die Stückliste
    (``consumption.needs``) braucht die Zahl *und* den Ort, die Arbeitsliste die Instanzen.
    Zwei Abfragen wären zwei Stände desselben Augenblicks.
    """
    return [u for _, u in _units_at(db, order, step.id)]


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
    holds = held_units(db, order, step, [u.id for u in units])
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
        instance = instances[unit.instance_id]
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
        if unit.id in holds:
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


def held_units(db: Session, order: Order, step: ProcessStep,
               unit_ids: list[int]) -> set[int]:
    """►►► **Welche Stücke hält dieses Modul fest?** ◄◄◄ — der **letzte Befund** zählt.

    Ein «nicht bestanden» hält an (§4.5): nichts rückt vor, und der Grund steht da. Der
    Halt ist eine **Auskunft über den letzten Befund**, keine Sperre – aufgehoben wird er
    durch einen **neuen Befund**, also durch erneutes Erfassen. Nach einer Nacharbeit ist
    das die Wiederholungsprüfung; genau so ist es gedacht.

    **Die Sackgasse lag nie hier.** Der Halt hatte immer einen Ausgang – die Oberfläche
    bot ihn nur nicht an: sie zeigte bei ``held`` **ausschliesslich** die Entscheidung und
    nie die Erfassung. Damit hatte sie eine Regel erfunden, die es im Dienst nicht gibt,
    und die erfundene Regel hatte keinen Schlüssel: wer die Abweichung anlegte und
    durchlaufen liess, bekam sein Stück zurück und stand wieder genau davor – derselbe
    Halt, dieselbe Meldung, und jeder weitere Anlauf legte nur eine weitere Abweichung an.

    Darum steht die Frage jetzt hier, an **einer** Stelle, statt in der Ansicht: ``held``
    ist eine abgeleitete Auskunft, und wer sie anzeigt, zeigt sie **neben** dem Weg nach
    vorn, nicht anstelle davon.
    """
    if not unit_ids:
        return set()
    latest = _latest_captures(db, order, step, unit_ids)
    return {u for u, cap in latest.items() if cap is not None and cap.result == "failed"}


def held_numbers(db: Session, order: Order, step: ProcessStep, *,
                 instance_object_id: int, group: str) -> list[str]:
    """Die Nummern **einer Gruppe dieser Instanz an diesem Modul** — erst auf Klick.

    Zwei Rollen, eine Frage – «welche Stücke, und wozu»:

    ``sample``   die **gezogenen**: für sie ist je ein Wertesatz zu erfassen (§9.3)
    ``failed``   die durchgefallenen – Vorauswahl für einen Abweichungsauftrag

    ``failed`` geht als Vorauswahl in einen ganz gewöhnlichen Auftragsentwurf – **kein
    neuer Mechanismus** (§4.1), nur eine andere Vorbelegung.

    **Die 100 %-Kontrolle braucht keine eigene Gruppe** (#713): sie ist ein
    Abweichungsauftrag über die übrigen Stücke mit der Stichprobe «alle» – der eine Weg,
    den es für alles gibt.

    **Erst auf Klick, nie auf Vorrat.** Keine dieser Listen steht in der Auftrags-Antwort:
    bei einer 6000er-Charge wären es tausende Nummern bei jedem Öffnen des Auftrags. Die
    Zahlen daneben (``step_work``) genügen für die Vorschau; die Nummern holt, wer sie
    wirklich braucht – also der, der gerade zu erfassen beginnt.
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
    elif group == "sample":
        drawn = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
        chosen = [u for u in units if u.id in drawn]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"«{group}» ist keine Gruppe – erlaubt: sample, failed.",
        )
    numbers = unit_numbers(db, chosen)
    return [numbers[u.id] for u in chosen]


def _order_number(db: Session, order_id: int) -> Optional[int]:
    """Die Objektnummer eines Auftrags – für Meldungen, die ihn nennen."""
    return db.query(Order.object_id).filter(Order.id == order_id).scalar()


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

    **«Abgeschlossen» heisst: den definierten Weg zu Ende gegangen** – nicht «das
    Ende-Objekt passiert». Der Unterschied zählt bei einem **Ausgang** (§4.6): wer
    ausgesondert wird, verlässt den Auftrag dort, und das ist das Ende seines Weges. Ein
    vierter Wert dafür wäre falsch; die Regel deckt ihn bereits.

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


def _loans_toward(db: Session, order_ids: list[int]) -> list[tuple[int, int, list[int]]]:
    """►►► **Die Rückführungs-Kette – gelesen an genau einer Stelle** (§3.5). ◄◄◄

    Je laufender Ausleihe, deren Stück aus einem der gefragten Aufträge stammt:
    ``(Stück, Auftrag, in dem es jetzt steckt, [Aufträge, in die es zurückkehrt])`` – die
    Liste von unten nach oben. Leiht A an B und B weiter an C, kehrt das Stück aus C nach
    B **und** nach A zurück, nur eine Stufe tiefer. Gefolgt wird ``return_to_order_id``,
    der Eigenschaft der **Verbindung**; eine gekappte Ausleihe endet die Kette, und das ist
    die Aussage «kommt nie zurück».

    Eingegrenzt wird auf die Stücke, die einen der gefragten Aufträge **verlassen** haben
    (geschlossene Zeile mit Zustandspunkt) – nur sie können dorthin zurückkehren. Zwei
    Leser fragen das: der Auftragsstatus (``waiting_counts``) und die Sperre bzw. das Bild
    (``returning_home``).
    """
    if not order_ids:
        return []
    left = (
        select(OrderUnit.instance_unit_id)
        .where(OrderUnit.order_id.in_(order_ids), OrderUnit.released_at.isnot(None),
               OrderUnit.current_step_id.isnot(None))
    )
    loans = db.query(OrderUnit.instance_unit_id, OrderUnit.order_id,
                     OrderUnit.return_to_order_id).filter(
        OrderUnit.released_at.is_(None), OrderUnit.return_to_order_id.isnot(None),
        OrderUnit.instance_unit_id.in_(left)).all()
    if not loans:
        return []
    upward: dict[tuple[int, int], int] = {
        (int(o), int(u)): int(r)
        for u, o, r in db.query(OrderUnit.instance_unit_id, OrderUnit.order_id,
                                OrderUnit.return_to_order_id).filter(
            OrderUnit.instance_unit_id.in_({u for u, _, _ in loans}),
            OrderUnit.return_to_order_id.isnot(None)).all()
    }
    out: list[tuple[int, int, list[int]]] = []
    for unit, holder, target in loans:
        homes: list[int] = []
        oid: Optional[int] = int(target)
        while oid is not None and oid not in homes:
            homes.append(oid)
            oid = upward.get((oid, int(unit)))
        out.append((int(unit), int(holder), homes))
    return out


def waiting_counts(db: Session, order_ids: list[int]) -> dict[int, int]:
    """Wie viele Stücke sind gerade **ausgeliehen und kommen zurück**? — je Auftrag.

    **Abgeleitet, nicht gespeichert.** Es wartet, wer noch mindestens eine offene
    rückführende Verbindung hat – über die ganze Kette (``_loans_toward``). Kappt eine
    Stufe die Rückführung, endet die Kette dort, und niemand darüber wartet weiter: jeder
    läuft mit weniger weiter, und wem nichts bleibt, dessen Ziel ist unerreichbar (§3.4).
    """
    wanted = set(order_ids)
    out: dict[int, int] = {}
    for _unit, _holder, homes in _loans_toward(db, list(wanted)):
        for oid in homes:
            if oid in wanted:
                out[oid] = out.get(oid, 0) + 1
    return out


def _away_points(db: Session, order: Order) -> dict[int, int]:
    """Je ausgeschertem Stück der Zustandspunkt, an dem es diesen Auftrag verlassen hat.

    Die Stelle steht schon da: beim Ausscheren wurde die Zeile geschlossen, ihr
    ``current_step_id`` aber nicht angetastet (§3.3). Nachzuschlagen gibt es nichts.
    """
    return {
        int(u): int(s)
        for u, s in db.query(OrderUnit.instance_unit_id, OrderUnit.current_step_id).filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.isnot(None),
            OrderUnit.current_step_id.isnot(None),
        ).all()
    }


def returning_home(db: Session, order: Order) -> dict[int, int]:
    """Welche ausgescherten Stücke kehren **hierher** zurück? — ``{Stück: Halter-Auftrag}``.

    Dieselbe Kette wie beim Auftragsstatus (``_loans_toward``), von diesem Auftrag aus
    gelesen. Zwei Fragen lesen sie: welches Modul **gesperrt** ist (``pending_returns``)
    und wo im Bild eine **Rückführungslinie** hingehört (``services/flow``).
    """
    return {unit: holder for unit, holder, homes in _loans_toward(db, [order.id])
            if order.id in homes}


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

    «Unterwegs» heisst: die Zugehörigkeit ist offen. «Abgebrochen» entsteht, wenn eine
    Abweichung **alle** Stücke nimmt und die Rückführung gekappt ist (Matrix S57 · S58 · S59).

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
            func.count(OrderUnit.id).filter(OrderUnit.released_at.is_(None)).label("alive"),
        )
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
    """Welche dieser Aufträge sind **Abweichungen**? — die Frage aus §2.

    **Ein Auftrag ist eine Abweichung, wenn sein Start vom Regelstart abwich.** Der
    Regelstart ist genau ein Zustand (``statuses.START_BEFORE`` = *Freigegeben*): so
    beginnt ein Stück, das regulär verfügbar war. Alles andere ist ein Zugriff auf
    Material, das gerade nicht zur Verfügung stand – und genau das ist dokumentationspflichtig.

    Die Regel **nennt darum keinen Status mehr**. Sie hiess einmal ``status_before ==
    im_prozess``, also «einem laufenden Auftrag entzogen» – technisch stimmig, fachlich zu
    eng: ein **gesperrtes** Stück wieder in Betrieb zu nehmen gehört zu keinem laufenden
    Auftrag und fiel deshalb heraus, obwohl es in der Qualitätssicherung der Musterfall
    einer Sonderfreigabe ist. Der Zweck des Labels ist die **Nachweisbarkeit**, nicht die
    Herkunft; ein Nachweis, der den auffälligsten Fall auslässt, ist keiner.

    Als Vergleich gegen den einen Regelstart ist sie zugleich die **einfachere** Regel und
    die haltbarere: ein künftiger Zustand ist automatisch eine Abweichung, ohne dass ihn
    jemand hier einträgt. Die Richtung stimmt – wer zu viel ausweist, dokumentiert; wer zu
    wenig ausweist, verliert den Nachweis.

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
            ProcessEvent.status_before != st.START_BEFORE,
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
    waiting = {
        int(sid) for (sid,) in db.query(OrderUnit.current_step_id).filter(
            OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None),
            OrderUnit.current_step_id.isnot(None)).distinct().all()
    }
    if not waiting:
        return None
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
