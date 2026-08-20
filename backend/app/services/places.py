"""**Wo ein Stück liegt** — ein Zeiger, kein Zustand.

Der Ort einer Einzelinstanz ist die Objektnummer ihres **Halters**, gespeichert an genau
einer Stelle (``instance_units.place_object_id``). Er ändert nie einen Status und nie
eine Zugehörigkeit; genau deshalb muss keine andere Regel im System von ihm wissen. Ein
Stück darf gesperrt, verbaut oder in einer Abweichung sein — sein Ort ist trotzdem
einfach der letzte Halter, an den es gebracht wurde.

**Gehalten wird die Einzelinstanz, Halter ist eine Objektnummer.** Diese Asymmetrie ist
kein Kompromiss, sondern die einzige mögliche Aussage: eine Einzelinstanz zieht bewusst
keine Objektnummer (``models/instance_unit``), es kann für sie gar kein Etikett geben —
also kann sie auch nicht gescannt und nicht als Ziel gewählt werden. Was man scannt, ist
das physische Ding, und das ist die **Instanz**: die Kiste, das Regal, die Palette.

**Kein Typfeld daneben.** Objektnummern sind systemweit eindeutig, der Typ ist daraus
ableitbar (``objects.resolve_object_type``). Der Vorgänger führte ``location_type`` neben
``location_id`` und musste einen entfallenen Wert (``'lagerplatz'``) tolerant zu ``None``
auflösen, weil er sonst jede Ansicht zerlegt hätte. Was es nicht gibt, kann nicht
veralten.

**Halter ist alles mit einer Objektnummer:** ein Regal, ein Behälter, eine Palette und
ein LKW sind **Instanzen**; Werk Nord und der Hauptsitz sind **Unternehmen**; ein
Mitarbeiter, ein Kunde und ein Spediteur sind **Benutzer**. Kein neuer Datensatztyp,
keine Whitelist.

**Die eine Regel des sonst dummen Feldes: keine Zyklen.** Läge Regal A im Behälter B und
B im Regal A, liefe die Kette im Kreis — und mit ihr jede Bestandsansicht. Verhindert
wird das beim Schreiben (``assert_placeable``), abgefangen beim Lesen (``MAX_STATIONS``).
Zwei Netze, weil Altbestand und Fremdschreiber die erste Prüfung nicht kennen.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from ..domain import modules
from ..models import (
    Article, CompanySettings, Instance, InstanceUnit, ProcessStep, UserProfile,
)

#: Wie viele Stationen eine Kette höchstens hat. Die Grenze ist ein **Netz**, keine
#: fachliche Aussage: eine echte Verschachtelung (Schraube › Behälter › Regal › Werk) ist
#: drei tief. Wer zehn erreicht, hat einen Zyklus, den die Schreibprüfung nicht gesehen
#: hat — und dann ist eine gekappte Kette besser als eine Ansicht, die hängt.
MAX_STATIONS = 10

#: Halter, die eine **Anschrift** tragen. Bei ihnen endet die Kette: sie sind der Ort in
#: der Welt, alles davor ist eine Verschachtelung darin.
ADDRESS_HOLDERS = ("user", "organization")


@dataclass(frozen=True)
class Station:
    """Eine Station der Kette — was sie ist, wie sie heisst, wo sie liegt."""

    object_id: int
    kind: str      # instance | user | organization
    label: str


def stations_for(db: Session, object_ids: Iterable[int]) -> dict[int, Station]:
    """Objektnummern → Halter, in **drei** Abfragen statt einer je Nummer.

    Das ist der Grund, warum diese Funktion existiert und nicht ``station_of`` in einer
    Schleife: eine Bestandsseite zeigt bis zu 60 Stücke, und jede Kettenstufe fragt
    erneut. Je Nummer eine Abfrage wären Hunderte — genau die N+1-Falle, an der die
    Ortsanzeige des Vorgängers hing.

    Eine Nummer, die zu nichts auflöst, fehlt im Ergebnis. Das ist eine Antwort («diesen
    Halter gibt es nicht mehr»), kein Fehler: die Anzeige zeigt dann die nackte Nummer,
    statt zu verschwinden.
    """
    ids = {int(o) for o in object_ids if o}
    if not ids:
        return {}
    out: dict[int, Station] = {}

    rows = (
        db.query(Instance.object_id, Instance.label, Article.name)
        .join(Article, Article.id == Instance.article_id)
        .filter(Instance.object_id.in_(ids))
        .all()
    )
    for object_id, label, article_name in rows:
        out[object_id] = Station(object_id, "instance", label or article_name or "Instanz")

    for user in db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all():
        out[user.object_id] = Station(user.object_id, "user", user.display_name)

    for co in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids)).all():
        out[co.object_id] = Station(co.object_id, "organization", co.company_name)

    return out


#: Wie viele Treffer eine Suche höchstens liefert. Eine Vorschlagsliste ist eine
#: Abkürzung, kein Katalog – wer scrollen muss, tippt schneller weiter.
SEARCH_LIMIT = 8


def search(db: Session, query: str, *, limit: int = SEARCH_LIMIT) -> list[Station]:
    """**Halter suchen — nach Nummer oder nach Namen.**

    Die Frage, die jede Zielort-Eingabe stellt: «001» soll die Objektnummer treffen,
    «Clemens» die Person, «Regal» den Behälter. Beides in einer Abfrage je Typ, statt
    den Aufrufer wählen zu lassen, wonach er sucht – er weiss es nicht, er tippt.

    **Gesucht wird nur, was auch Halter sein kann.** Das ist dieselbe Menge, die
    ``station_of`` auflöst und die ``assert_placeable`` durchlässt: eine Vorschlagsliste,
    die etwas anbietet, das die Prüfung danach abweist, wäre schlimmer als keine.

    Artikel und Aufträge stehen darum nicht darin, obwohl sie Objektnummern tragen.
    """
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q.lower()}%"
    out: list[Station] = []

    rows = (
        db.query(Instance.object_id, Instance.label, Article.name)
        .join(Article, Article.id == Instance.article_id)
        .filter(
            Instance.is_active.is_(True),
            or_(
                func.cast(Instance.object_id, String).like(f"%{q}%"),
                func.lower(func.coalesce(Instance.label, "")).like(like),
                func.lower(Article.name).like(like),
            ),
        )
        .order_by(Instance.object_id.desc())
        .limit(limit)
        .all()
    )
    for object_id, label, article_name in rows:
        out.append(Station(object_id, "instance", label or article_name or "Instanz"))

    users = (
        db.query(UserProfile)
        .filter(
            UserProfile.object_id.isnot(None),
            UserProfile.is_active.is_(True),
            or_(
                func.cast(UserProfile.object_id, String).like(f"%{q}%"),
                func.lower(func.coalesce(UserProfile.first_name, "")).like(like),
                func.lower(func.coalesce(UserProfile.last_name, "")).like(like),
                func.lower(func.coalesce(UserProfile.company_name, "")).like(like),
                func.lower(func.coalesce(UserProfile.email, "")).like(like),
            ),
        )
        .order_by(UserProfile.object_id.desc())
        .limit(limit)
        .all()
    )
    out.extend(Station(u.object_id, "user", u.display_name) for u in users)

    companies = (
        db.query(CompanySettings)
        .filter(
            CompanySettings.object_id.isnot(None),
            CompanySettings.is_active.is_(True),
            or_(
                func.cast(CompanySettings.object_id, String).like(f"%{q}%"),
                func.lower(func.coalesce(CompanySettings.company_name, "")).like(like),
            ),
        )
        .order_by(CompanySettings.object_id.desc())
        .limit(limit)
        .all()
    )
    out.extend(Station(c.object_id, "organization", c.company_name) for c in companies)

    return out[:limit]


def station_of(db: Session, object_id: int) -> Optional[Station]:
    """Ein einzelner Halter — dieselbe Frage, andere Körnung."""
    return stations_for(db, [object_id]).get(int(object_id))


def chain(db: Session, place_object_id: Optional[int]) -> list[Station]:
    """Die Kette von innen nach aussen: Behälter › Regal › Werk Nord.

    Sie beginnt beim **unmittelbaren** Halter und endet, wenn einer davon eine Anschrift
    trägt (Benutzer oder Unternehmen), wenn er nirgends liegt, oder wenn er nicht mehr
    auflösbar ist. Eine leere Liste heisst schlicht: standortlos.

    **Zyklensicher zweifach** — gesehene Nummern und eine harte Obergrenze. Die
    Schreibprüfung verhindert Zyklen bereits; hier steht das Netz für alles, was sie nie
    gesehen hat.
    """
    if not place_object_id:
        return []
    return chains_for(db, [int(place_object_id)]).get(int(place_object_id), [])


def _places_of_instances(db: Session, object_ids: list[int]) -> dict[int, int]:
    """**Wo liegen diese Instanzen?** — eine Abfrage für alle, nicht eine je Instanz.

    Der Ort hängt am Stück, nicht an der Gruppe (zwei Schrauben einer Charge dürfen an
    zwei Orten liegen). Eine Instanz als *Halter* ist aber ein physisches Ding – ein
    Regal, ein Behälter –, und das liegt an einem Ort. Beides trifft sich hier: liegen
    alle ihre Stücke am selben Halter, ist das ihr Ort; sonst endet die Kette. Das deckt
    den Normalfall (ein serialisiertes Regal = ein Stück) mit ab, ohne ihn als Sonderfall
    zu behandeln – und es erfindet keine Antwort, wo es keine gibt.
    """
    if not object_ids:
        return {}
    rows = (
        db.query(Instance.object_id, InstanceUnit.place_object_id)
        .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
        .filter(Instance.object_id.in_(set(object_ids)))
        .distinct()
        .all()
    )
    seen: dict[int, Optional[int]] = {}
    for object_id, place in rows:
        # Zweiter, abweichender Ort → die Instanz liegt nicht an EINEM Ort. Hier endet
        # die Kette, statt sich einen der beiden auszusuchen.
        seen[object_id] = place if object_id not in seen else (
            seen[object_id] if seen[object_id] == place else None
        )
    return {o: p for o, p in seen.items() if p is not None}


def chains_for(db: Session, holder_ids: Iterable[int]) -> dict[int, list[Station]]:
    """Die Ketten **mehrerer** Halter — stufenweise, nicht je Halter einzeln.

    Das ist der Unterschied zwischen einer Bestandsseite, die lädt, und einer, die
    hängt: 60 Stücke in fünf Regalen sind **fünf** Ketten, und jede Stufe kostet
    dieselben vier Abfragen, egal wie viele Halter noch offen sind. Je Halter einzeln
    aufzulösen wären es fünf mal Tiefe mal vier – dieselbe Antwort, N+1-mal geholt.

    Gleiche Halter teilen sich ihre Kette; sie wird einmal gebaut und mehrfach
    zugeordnet.
    """
    heads = {int(h) for h in holder_ids if h}
    if not heads:
        return {}
    chains: dict[int, list[Station]] = {h: [] for h in heads}
    seen: dict[int, set[int]] = {h: set() for h in heads}
    # Welche Ketten warten gerade auf welchen Halter? (Halter → Ketten, die dort stehen)
    frontier: dict[int, list[int]] = {h: [h] for h in heads}

    for _ in range(MAX_STATIONS):
        if not frontier:
            break
        stations = stations_for(db, frontier)
        follow: list[int] = []
        for current, owners in frontier.items():
            station = stations.get(current)
            if station is None:
                continue
            for head in owners:
                if current in seen[head]:
                    continue
                seen[head].add(current)
                chains[head].append(station)
            if station.kind not in ADDRESS_HOLDERS:
                follow.append(current)

        nxt: dict[int, list[int]] = {}
        for current, place in _places_of_instances(db, follow).items():
            for head in frontier.get(current, []):
                if place not in seen[head]:
                    nxt.setdefault(place, []).append(head)
        frontier = nxt
    return chains


def assert_placeable(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """Darf dieses Ziel diese Stücke aufnehmen? — die eine Prüfung vor dem Schreiben.

    Drei Fragen, und alle drei müssen hier gestellt werden, weil das Feld danach nichts
    mehr prüft: **gibt es den Halter**, ist er **nicht die eigene Instanz** (ein Ding
    liegt nicht in sich selbst), und **entsteht kein Zyklus** (das Ziel darf nicht
    irgendwo in einem der bewegten Stücke liegen).
    """
    station = station_of(db, target)
    if station is None:
        raise HTTPException(
            status_code=404,
            detail=(f"Die Objektnummer {target} gibt es nicht – ein Ziel muss ein Regal, "
                    f"eine Person oder ein Unternehmen sein."),
        )
    own = {i.object_id for i in _instances_of(db, units)}
    if target in own:
        raise HTTPException(
            status_code=400,
            detail=f"Instanz {target} kann nicht in sich selbst liegen.",
        )
    inside = {s.object_id for s in chain(db, target)}
    if own & inside:
        raise HTTPException(
            status_code=400,
            detail=(f"«{station.label}» liegt selbst in dem, was bewegt werden soll – "
                    f"das ergäbe einen Ort, der im Kreis führt."),
        )
    return station


def _instances_of(db: Session, units: list[InstanceUnit]) -> list[Instance]:
    ids = {u.instance_id for u in units}
    return db.query(Instance).filter(Instance.id.in_(ids)).all() if ids else []


def place(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """**Die eine Schreibstelle.** Prüft, dann setzt — und sonst nichts.

    Kein Statuswechsel, keine Zugehörigkeit, kein Log: dass ein Stück bewegt wurde, hält
    der Ereignis-Log an seinem Modul fest (``process.confirm_step``), und dort steht es
    mit Herkunft und Ziel. Ein zweiter Eintrag hier wäre eine zweite Wahrheit über
    denselben Vorgang.
    """
    station = assert_placeable(db, units=units, target=target)
    for unit in units:
        unit.place_object_id = target
    return station


def apply_for_step(
    db: Session, *, step: ProcessStep, units: list[InstanceUnit],
    target: Optional[int], transport: Optional[str],
) -> dict[int, dict[str, object]]:
    """**Was dieses Modul am Ort ändert** — und nichts, wenn es keiner ist, der bewegt.

    Die Ausführungsstelle (``process.confirm_step``) ruft das für **jedes** Modul auf und
    fragt nicht nach dem Typ; die Antwort ist leer, wo nichts zu bewegen ist. Dieselbe
    Bauart wie ``consumption.plan`` und ``capture.record_for_step``: der Fach-Dienst kennt
    sein Modul, der eine Mechanismus kennt keines.

    Zurück kommt, **was passiert ist** – je Stück Herkunft und Ziel. Das reist als
    Payload in den Ereignis-Log, und damit steht die Bewegung dort, wo die Historie
    ohnehin steht (§7.2), statt in einer zweiten Tabelle daneben.
    """
    move = modules.get(step.module_type).movement_for(
        step.config, target=target, transport=transport,
    )
    if move is None:
        return {}
    # **Erst lesen, dann schreiben**: die Herkunft gibt es nach dem Setzen nicht mehr.
    before = {u.id: u.place_object_id for u in units}
    station = place(db, units=units, target=move.target)
    return {
        u.id: {
            "place": {"from": before[u.id], "to": move.target, "label": station.label},
            "transport": move.transport,
        }
        for u in units
    }


def for_units(db: Session, units: Iterable[InstanceUnit]) -> dict[int, list[Station]]:
    """Je Einzelinstanz ihre Kette — aufgelöst **je Halter**, nicht je Stück.

    Das ist die Stelle, an der die Skalierbarkeit entschieden wird: 60 Schrauben in einem
    Regal sind **eine** Kette, nicht sechzig. Wer hier je Zeile auflöst, baut die
    N+1-Falle, an der die Ortsanzeige des Vorgängersystems hing.
    """
    rows = [u for u in units if u.place_object_id]
    chains = chains_for(db, {u.place_object_id for u in rows})
    return {u.id: chains.get(int(u.place_object_id), []) for u in rows}


def counts_at(db: Session, object_id: int) -> int:
    """Wie viele Stücke liegen unmittelbar an dieser Nummer? (Gegenrichtung, lesend.)"""
    return (
        db.query(func.count(InstanceUnit.id))
        .filter(InstanceUnit.place_object_id == object_id)
        .scalar() or 0
    )
