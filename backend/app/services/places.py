"""**Wo ein Stück liegt** — ein Zeiger, kein Zustand.

Der Ort einer Einzelinstanz ist ihr **Halter**, gespeichert an genau einer Stelle
(``instance_units``). Er ändert nie einen Status und nie eine Zugehörigkeit; genau
deshalb muss keine andere Regel im System von ihm wissen. Ein Stück darf gesperrt,
verbaut oder in einer Abweichung sein — sein Ort ist trotzdem einfach der letzte Halter,
an den es gebracht wurde.

**Es gibt zwei Arten von Halter, und die Genauigkeit des Ortes ist die Genauigkeit
seiner Quelle:**

``place_object_id``
    Ein **gescannter** Halter: Instanz (Regal, Behälter, LKW), Benutzer, Unternehmen.
    Was man scannt, ist ein Etikett — und ein Etikett hat die **Instanz**. Feiner geht es
    nicht, ohne zu raten, welches Stück der Charge gemeint war.

``place_unit_id``
    Ein **Träger**: das eine Stück, in dem dieses Stück steckt. Beim Verbauen kennt das
    Modul es genau (``consumption.plan`` teilt je Produkt-Stück zu) — diese Genauigkeit
    wegzuwerfen wäre eine erfundene Unschärfe. Und die Instanz-Nummer stattdessen wäre
    eine **Gruppe**: «in 100000123» sagt bei 600 Getrieben nicht, in welchem.

Höchstens eines von beiden ist gesetzt (``CHECK``, Migration 112) — der Ort bleibt
**eine** Aussage, sie hat nur zwei mögliche Formen. Beides zusammen heisst hier
``Place``.

**Nicht die Genealogie.** Der Log sagt, *worin* verbaut wurde (``payload.into``) —
unveränderlich, überlebt die Demontage. Diese Spalten sagen, *wo es jetzt liegt*, und
werden beim Ausbau geräumt. Dass die beiden auseinander laufen können, ist der Beweis,
dass es zwei Fragen sind (PROCESS_CORE §9.6).

**Kein Typfeld daneben.** Objektnummern sind systemweit eindeutig, der Typ ist daraus
ableitbar (``objects.resolve_object_type``). Der Vorgänger führte ``location_type`` neben
``location_id`` und musste einen entfallenen Wert (``'lagerplatz'``) tolerant zu ``None``
auflösen, weil er sonst jede Ansicht zerlegt hätte. Was es nicht gibt, kann nicht
veralten.

**Die eine Regel des sonst dummen Feldes: keine Zyklen.** Läge Regal A im Behälter B und
B im Regal A, liefe die Kette im Kreis — und mit ihr jede Bestandsansicht. Verhindert
wird das beim Schreiben (``assert_placeable``), abgefangen beim Lesen (``seen`` +
``MAX_STATIONS``). Zwei Netze, weil Altbestand und Fremdschreiber die erste Prüfung
nicht kennen.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..domain import modules
from ..models import (
    Article, CompanySettings, Instance, InstanceUnit, ProcessStep, UserProfile,
)
from . import lookup
from .instances import unit_number

#: Wie viele Stationen eine Kette höchstens hat. Die Grenze ist ein **Netz**, keine
#: fachliche Aussage: eine echte Verschachtelung (Schraube › Getriebe › Behälter › Regal
#: › Werk) ist vier tief. Wer zehn erreicht, hat einen Zyklus, den die Schreibprüfung
#: nicht gesehen hat — und dann ist eine gekappte Kette besser als eine Ansicht, die hängt.
MAX_STATIONS = 10

#: Halter, die eine **Anschrift** tragen. Bei ihnen endet die Kette: sie sind der Ort in
#: der Welt, alles davor ist eine Verschachtelung darin.
ADDRESS_HOLDERS = ("user", "organization")

#: Die beiden Arten von Halter. ``OBJECT`` trägt eine Objektnummer (Instanz · Benutzer ·
#: Unternehmen), ``UNIT`` den internen Schlüssel einer Einzelinstanz — die hat bewusst
#: keine Objektnummer (PROCESS_CORE §2.2).
OBJECT, UNIT = "object", "unit"

#: **Ein Ort** – die Art und der Schlüssel. Ein Tupel und keine Klasse, weil er als
#: Schlüssel in Wörterbüchern steht: die Kettenauflösung gruppiert nach ihm.
Place = tuple[str, int]


@dataclass(frozen=True)
class Station:
    """Eine Station der Kette — was sie ist und wie sie heisst.

    ``object_id`` ist immer der **Datensatz**, den ein Klick öffnet. Bei einem Träger ist
    das seine **Instanz**: das Stück selbst hat keinen eigenen Datensatz. Wie es heisst,
    steht dann in ``number`` (``100000123-3``) – die Anzeige zieht sie der Objektnummer
    vor, weil sie die genauere Aussage ist.
    """

    object_id: int
    kind: str                      # instance | user | organization | unit
    label: str
    number: Optional[str] = None   # nur bei kind == "unit"


def place_of(unit: InstanceUnit) -> Optional[Place]:
    """**Wo liegt dieses Stück?** — die eine Lesestelle für die beiden Spalten.

    Wer sie einzeln liest, baut die Fallunterscheidung an jeder Stelle nach; und die
    Stelle, an der jemand die zweite vergisst, ist die, an der ein verbautes Stück
    plötzlich standortlos aussieht.
    """
    if unit.place_unit_id:
        return (UNIT, int(unit.place_unit_id))
    if unit.place_object_id:
        return (OBJECT, int(unit.place_object_id))
    return None


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


def unit_stations(db: Session, unit_ids: Iterable[int]) -> dict[int, Station]:
    """Träger-Stücke → Station, in **einer** Abfrage über drei Tabellen.

    Die Station trägt die Objektnummer der **Instanz** (dorthin führt der Klick) und die
    Stück-Nummer als Beschriftung – ein Stück hat keinen eigenen Datensatz, aber einen
    eindeutigen Namen.
    """
    ids = {int(u) for u in unit_ids if u}
    if not ids:
        return {}
    rows = (
        db.query(InstanceUnit, Instance, Article.name)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .join(Article, Article.id == Instance.article_id)
        .filter(InstanceUnit.id.in_(ids))
        .all()
    )
    return {
        unit.id: Station(
            instance.object_id, UNIT,
            instance.label or article_name or "Einzelinstanz",
            number=unit_number(instance, unit),
        )
        for unit, instance, article_name in rows
    }


def _stations(db: Session, places: Iterable[Place]) -> dict[Place, Station]:
    """Orte beider Arten → Stationen, batchweise je Art."""
    wanted = set(places)
    objects = stations_for(db, [pid for kind, pid in wanted if kind == OBJECT])
    units = unit_stations(db, [pid for kind, pid in wanted if kind == UNIT])
    out: dict[Place, Station] = {}
    for place in wanted:
        kind, pid = place
        found = objects.get(pid) if kind == OBJECT else units.get(pid)
        if found is not None:
            out[place] = found
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

    Artikel und Aufträge stehen darum nicht darin, obwohl sie Objektnummern tragen – und
    **Träger-Stücke** ebenso wenig: sie entstehen beim Verbauen, nicht beim Scannen.
    """
    q = (query or "").strip()
    if not q:
        return []
    out: list[Station] = []

    # **Dieselbe Bedingung wie jedes andere Referenzfeld** (``services/lookup``) – hier
    # nur dreimal angewandt, weil ein Halter dreierlei sein kann.
    rows = (
        db.query(Instance.object_id, Instance.label, Article.name)
        .join(Article, Article.id == Instance.article_id)
        .filter(
            Instance.is_active.is_(True),
            lookup.matches(q, Instance.object_id, Instance.label, Article.name),
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
            lookup.matches(q, UserProfile.object_id, UserProfile.first_name,
                           UserProfile.last_name, UserProfile.company_name,
                           UserProfile.email),
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
            lookup.matches(q, CompanySettings.object_id, CompanySettings.company_name),
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


def describe(db: Session, place: Optional[Place]) -> Optional[Station]:
    """Ein Ort beider Arten → seine Station. Für Meldungen und Antworten."""
    return _stations(db, [place]).get(place) if place else None


def chain(db: Session, place: Optional[Place]) -> list[Station]:
    """Die Kette von innen nach aussen: Getriebe › Behälter › Regal › Werk Nord.

    Sie beginnt beim **unmittelbaren** Halter und endet, wenn einer davon eine Anschrift
    trägt (Benutzer oder Unternehmen), wenn er nirgends liegt, oder wenn er nicht mehr
    auflösbar ist. Eine leere Liste heisst schlicht: standortlos.

    **Zyklensicher zweifach** — gesehene Orte und eine harte Obergrenze. Die
    Schreibprüfung verhindert Zyklen bereits; hier steht das Netz für alles, was sie nie
    gesehen hat.
    """
    if not place:
        return []
    return chains_for(db, [place]).get(place, [])


def _places_of_instances(db: Session, object_ids: list[int]) -> dict[int, Place]:
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
        db.query(
            Instance.object_id,
            InstanceUnit.place_object_id,
            InstanceUnit.place_unit_id,
        )
        .join(InstanceUnit, InstanceUnit.instance_id == Instance.id)
        .filter(Instance.object_id.in_(set(object_ids)))
        .distinct()
        .all()
    )
    seen: dict[int, Optional[Place]] = {}
    for object_id, place_object_id, place_unit_id in rows:
        place: Optional[Place] = (
            (UNIT, int(place_unit_id)) if place_unit_id
            else (OBJECT, int(place_object_id)) if place_object_id
            else None
        )
        # Zweiter, abweichender Ort → die Instanz liegt nicht an EINEM Ort. Hier endet
        # die Kette, statt sich einen der beiden auszusuchen.
        seen[object_id] = place if object_id not in seen else (
            seen[object_id] if seen[object_id] == place else None
        )
    return {o: p for o, p in seen.items() if p is not None}


def _places_of_units(db: Session, unit_ids: list[int]) -> dict[int, Place]:
    """**Wo liegen diese Träger-Stücke?** — die Fortsetzung der Kette über ein Stück.

    Ein Getriebe, in dem eine Schraube steckt, liegt selbst irgendwo; ohne diesen Schritt
    endete die Kette beim Getriebe und die Schraube hätte keine Anschrift.
    """
    if not unit_ids:
        return {}
    rows = (
        db.query(InstanceUnit.id, InstanceUnit.place_object_id, InstanceUnit.place_unit_id)
        .filter(InstanceUnit.id.in_(set(unit_ids)))
        .all()
    )
    out: dict[int, Place] = {}
    for unit_id, place_object_id, place_unit_id in rows:
        if place_unit_id:
            out[unit_id] = (UNIT, int(place_unit_id))
        elif place_object_id:
            out[unit_id] = (OBJECT, int(place_object_id))
    return out


def _next_places(db: Session, places: Iterable[Place]) -> dict[Place, Place]:
    """Wo liegt der Halter selbst? — batchweise je Art, nie je Halter."""
    wanted = set(places)
    out: dict[Place, Place] = {}
    for object_id, place in _places_of_instances(
        db, [pid for kind, pid in wanted if kind == OBJECT]
    ).items():
        out[(OBJECT, object_id)] = place
    for unit_id, place in _places_of_units(
        db, [pid for kind, pid in wanted if kind == UNIT]
    ).items():
        out[(UNIT, unit_id)] = place
    return out


def _walk(db: Session, places: Iterable[Place]) -> dict[Place, list[tuple[Place, Station]]]:
    """Die Ketten **mehrerer** Halter — stufenweise, nicht je Halter einzeln.

    Das ist der Unterschied zwischen einer Bestandsseite, die lädt, und einer, die
    hängt: 60 Stücke in fünf Regalen sind **fünf** Ketten, und jede Stufe kostet
    dieselben Abfragen, egal wie viele Halter noch offen sind. Je Halter einzeln
    aufzulösen wären es fünf mal Tiefe mal vier – dieselbe Antwort, N+1-mal geholt.

    Gleiche Halter teilen sich ihre Kette; sie wird einmal gebaut und mehrfach
    zugeordnet.

    Zurück kommt je Station **beides**: der Ort (womit sich Ketten vergleichen lassen –
    ein Träger und seine Instanz tragen dieselbe Objektnummer) und die Station (womit
    sie sich anzeigen lässt). Ein Lauf, zwei Projektionen; zwei Läufe wären zwei
    Antworten auf dieselbe Frage.
    """
    heads = {p for p in places if p}
    if not heads:
        return {}
    chains: dict[Place, list[tuple[Place, Station]]] = {h: [] for h in heads}
    seen: dict[Place, set[Place]] = {h: set() for h in heads}
    # Welche Ketten warten gerade auf welchen Halter? (Halter → Ketten, die dort stehen)
    frontier: dict[Place, list[Place]] = {h: [h] for h in heads}

    for _ in range(MAX_STATIONS):
        if not frontier:
            break
        stations = _stations(db, frontier)
        follow: list[Place] = []
        for current, owners in frontier.items():
            station = stations.get(current)
            if station is None:
                continue
            for head in owners:
                if current in seen[head]:
                    continue
                seen[head].add(current)
                chains[head].append((current, station))
            if station.kind not in ADDRESS_HOLDERS:
                follow.append(current)

        nxt: dict[Place, list[Place]] = {}
        for current, place in _next_places(db, follow).items():
            for head in frontier.get(current, []):
                if place not in seen[head]:
                    nxt.setdefault(place, []).append(head)
        frontier = nxt
    return chains


def chains_for(db: Session, places: Iterable[Place]) -> dict[Place, list[Station]]:
    """Die Ketten mehrerer Halter, **zum Anzeigen** — von innen nach aussen."""
    return {head: [station for _, station in row]
            for head, row in _walk(db, places).items()}


# ---------------------------------------------------------------------------
# Schreiben — genau hier, sonst nirgends
# ---------------------------------------------------------------------------

def _assert_placeable(db: Session, *, units: list[InstanceUnit], target: Place,
                      label: str) -> None:
    """Darf dieses Ziel diese Stücke aufnehmen? — die Prüfung vor **jedem** Schreiben.

    Zwei Fragen, und beide müssen hier gestellt werden, weil das Feld danach nichts mehr
    prüft: ist das Ziel eines der bewegten Stücke selbst (ein Ding liegt nicht in sich
    selbst), und liegt es **in** einem von ihnen (das ergäbe einen Ort, der im Kreis
    führt).

    Verglichen werden **Orte**, nicht Beschriftungen: ein Träger und seine Instanz tragen
    dieselbe Objektnummer, und ein Vergleich über sie hielte ein Stück für sein eigenes
    Regal.
    """
    own: set[Place] = {(OBJECT, i.object_id) for i in _instances_of(db, units)}
    own |= {(UNIT, u.id) for u in units}
    if target in own:
        raise HTTPException(
            status_code=400,
            detail=f"«{label}» kann nicht in sich selbst liegen.",
        )
    inside = {place for place, _ in _walk(db, [target]).get(target, [])}
    if own & inside:
        raise HTTPException(
            status_code=400,
            detail=(f"«{label}» liegt selbst in dem, was bewegt werden soll – "
                    f"das ergäbe einen Ort, der im Kreis führt."),
        )


def assert_placeable(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """Ein **gescanntes** Ziel prüfen: gibt es den Halter, und bildet er keinen Kreis?"""
    station = station_of(db, target)
    if station is None:
        raise HTTPException(
            status_code=404,
            detail=(f"Die Objektnummer {target} gibt es nicht – ein Ziel muss ein Regal, "
                    f"eine Person oder ein Unternehmen sein."),
        )
    _assert_placeable(db, units=units, target=(OBJECT, int(target)), label=station.label)
    return station


def _instances_of(db: Session, units: list[InstanceUnit]) -> list[Instance]:
    ids = {u.instance_id for u in units}
    return db.query(Instance).filter(Instance.id.in_(ids)).all() if ids else []


def place(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """**Die eine Schreibstelle für einen gescannten Halter.** Prüft, dann setzt.

    Kein Statuswechsel, keine Zugehörigkeit, kein Log: dass ein Stück bewegt wurde, hält
    der Ereignis-Log an seinem Modul fest (``process.confirm_step``), und dort steht es
    mit Herkunft und Ziel. Ein zweiter Eintrag hier wäre eine zweite Wahrheit über
    denselben Vorgang.
    """
    station = assert_placeable(db, units=units, target=target)
    for unit in units:
        unit.place_object_id = int(target)
        unit.place_unit_id = None
    return station


def place_in(db: Session, *, units: list[InstanceUnit], carrier: InstanceUnit) -> None:
    """**Die eine Schreibstelle für einen Träger** — dieses Stück steckt jetzt in jenem.

    Gerufen vom Verbrauch, sonst von niemandem: nur dort steht fest, **welches** Stück
    aufnimmt. Gescannt werden kann ein Träger nicht — er hat kein Etikett.
    """
    if not units:
        return
    _assert_placeable(
        db, units=units, target=(UNIT, carrier.id),
        label=f"Einzelinstanz {carrier.id}",
    )
    for unit in units:
        unit.place_unit_id = carrier.id
        unit.place_object_id = None


def forget(db: Session, units: list[InstanceUnit]) -> None:
    """**Der Ort gilt nicht mehr** — die zweite Form von ``place``.

    Gerufen, wenn ein Stück zur **Historie** wird (``Status.stock``): es liegt dann nicht
    mehr im Regal, und der alte Halter wäre eine Behauptung über etwas, das dort nicht
    mehr ist. Wer stattdessen einen neuen Ort hat – ein verbautes Stück seinen Träger –,
    setzt ihn im selben Zug.
    """
    for unit in units:
        unit.place_object_id = None
        unit.place_unit_id = None


def apply_for_step(
    db: Session, *, step: ProcessStep, units: list[InstanceUnit],
    target: Optional[int], bought: bool = False,
) -> dict[int, dict[str, object]]:
    """**Was dieses Modul am Ort ändert** — und nichts, wenn es keiner ist, der bewegt.

    Die Ausführungsstelle (``process.confirm_step``) ruft das für **jedes** Modul auf und
    fragt nicht nach dem Typ; die Antwort ist leer, wo nichts zu bewegen ist. Dieselbe
    Bauart wie ``consumption.plan`` und ``capture.record_for_step``: der Fach-Dienst kennt
    sein Modul, der eine Mechanismus kennt keines.

    Zurück kommt, **was passiert ist** – je Stück Herkunft und Ziel. Das reist als
    Payload in den Ereignis-Log, und damit steht die Bewegung dort, wo die Historie
    ohnehin steht (§7.2), statt in einer zweiten Tabelle daneben.

    ``bought`` ist **abgeleitet** (gibt es einen Einkaufs-Beleg an diesem Modul?) und
    steht im Log, weil er dort Geschichte ist. Er ist keine Eingabe: die frühere
    Transportart war eine, und eine Eingabe kann dem widersprechen, was wirklich
    geschehen ist.
    """
    move = modules.get(step.module_type).movement_for(step.config, target=target)
    if move is None:
        return {}
    # **Erst lesen, dann schreiben**: die Herkunft gibt es nach dem Setzen nicht mehr.
    # Sie kann beide Formen haben (Halter oder Träger) – darum der ``Place``, nicht die
    # Objektnummer allein: ein ausgebautes Stück käme sonst «aus dem Nichts».
    before = {u.id: place_of(u) for u in units}
    station = place(db, units=units, target=move.target)
    return {
        u.id: {
            "place": {"from": before[u.id], "to": move.target, "label": station.label},
            "bought": bought,
        }
        for u in units
    }


# ---------------------------------------------------------------------------
# Lesen — für Anzeige und für die Ortsprüfung eines Moduls
# ---------------------------------------------------------------------------

def for_units(db: Session, units: Iterable[InstanceUnit]) -> dict[int, list[Station]]:
    """Je Einzelinstanz ihre Kette — aufgelöst **je Halter**, nicht je Stück.

    Das ist die Stelle, an der die Skalierbarkeit entschieden wird: 60 Schrauben in einem
    Regal sind **eine** Kette, nicht sechzig. Wer hier je Zeile auflöst, baut die
    N+1-Falle, an der die Ortsanzeige des Vorgängersystems hing.
    """
    at = {u.id: place_of(u) for u in units}
    chains = chains_for(db, [p for p in at.values() if p])
    return {uid: chains.get(p, []) for uid, p in at.items() if p}


def common_holder(units: Iterable[InstanceUnit]) -> Optional[Place]:
    """**Der Ort, an dem ALLE liegen** — oder ``None``.

    Die Frage eines Moduls, das Material an einen Ort verlangt: wo arbeitet es? Liegen
    seine Stücke an verschiedenen Orten (oder nirgends), gibt es darauf keine Antwort –
    und dann wird auch keine verlangt. Eine erfundene wäre schlimmer: sie sperrte ein
    Modul auf einen Ort, den nur ein Teil der Stücke teilt.
    """
    found: Optional[Place] = None
    for index, unit in enumerate(units):
        here = place_of(unit)
        if here is None or (index and here != found):
            return None
        found = here
    return found


def at_holder(db: Session, units: list[InstanceUnit], holder: Place) -> set[int]:
    """**Welche dieser Stücke liegen an (oder in) diesem Halter?**

    «Am Ort» heisst nicht «identische Nummer»: die Schraube in der Kiste, die auf
    Werkbank 5 steht, **ist** auf Werkbank 5. Geprüft wird darum, ob der verlangte Halter
    in der **Kette** des Stücks steht – und die gibt es bereits, batchweise je Halter.
    """
    if not units:
        return set()
    at = {u.id: place_of(u) for u in units}
    walked = _walk(db, [p for p in at.values() if p])
    covered = {
        head for head, row in walked.items()
        if head == holder or any(place == holder for place, _ in row)
    }
    return {uid for uid, place in at.items() if place in covered}


def counts_at(db: Session, object_id: int) -> int:
    """Wie viele Stücke liegen unmittelbar an dieser Nummer? (Gegenrichtung, lesend.)"""
    return (
        db.query(func.count(InstanceUnit.id))
        .filter(InstanceUnit.place_object_id == object_id)
        .scalar() or 0
    )
