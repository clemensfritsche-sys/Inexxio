"""**Wo ein Stück liegt** — ein Zeiger, kein Zustand.

Der Ort einer Einzelinstanz ist ihr **Halter**, gespeichert nur in ``instance_units``. Er
ändert nie Status oder Zugehörigkeit; darum muss keine andere Regel von ihm wissen.

``place_object_id``
    Ein **gescannter** Halter: Instanz (Regal, Behälter, LKW), Benutzer, Unternehmen –
    gescannt wird das Etikett der Instanz.
``place_unit_id``
    Ein **Träger**: das eine Stück, in dem dieses steckt (beim Verbauen genau bekannt).

Höchstens eines ist gesetzt (``CHECK``); zusammen heisst es ``Place``. Kein Typfeld – der
Typ folgt aus der Objektnummer (``objects.resolve_object_type``). **Nicht die
Genealogie**: *worin* verbaut wurde, sagt der Log (``payload.into``); hier steht, *wo es
jetzt liegt* (PROCESS_CORE §9.6). **Keine Zyklen**: verhindert beim Schreiben
(``assert_placeable``), abgefangen beim Lesen (``seen`` + ``MAX_STATIONS``).
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from ..models import (
    Article, CompanySettings, Instance, InstanceUnit, ProcessStep, UserProfile,
)
from . import lookup, people, sites
from .instances import number_of, unit_number
from ..domain.errors import Invalid, NotFound

#: Wie viele Stationen eine Kette höchstens hat – ein **Netz** gegen Zyklen, keine fachliche
#: Aussage (echte Verschachtelung ist etwa vier tief).
MAX_STATIONS = 10

#: Halter, die eine **Anschrift** tragen – bei ihnen endet die Kette.
ADDRESS_HOLDERS = ("user", "organization")

#: Die beiden Arten von Halter. ``OBJECT`` trägt eine Objektnummer, ``UNIT`` den internen
#: Schlüssel einer Einzelinstanz (die hat keine Objektnummer, PROCESS_CORE §2.2).
OBJECT, UNIT = "object", "unit"

#: **Ein Ort** – Art und Schlüssel; ein Tupel, weil er als Schlüssel in Wörterbüchern steht.
Place = tuple[str, int]


@dataclass(frozen=True)
class Station:
    """Eine Station der Kette — was sie ist und wie sie heisst.

    ``object_id`` ist der Datensatz, den ein Klick öffnet (bei einem Träger seine Instanz);
    ``number`` (``100000123-3``) nennt das Stück genauer.
    """

    object_id: int
    kind: str                      # instance | user | organization | unit
    label: str
    number: Optional[str] = None   # nur bei kind == "unit"


def place_from(place_object_id: Optional[int], place_unit_id: Optional[int]) -> Optional[Place]:
    """**Die zwei Spalten eines Stücks → sein Ort** – die eine Lesestelle, auch für Abfragen,
    die nur die Spalten holen."""
    if place_unit_id:
        return (UNIT, int(place_unit_id))
    if place_object_id:
        return (OBJECT, int(place_object_id))
    return None


def place_of(unit: InstanceUnit) -> Optional[Place]:
    """**Wo liegt dieses Stück?**"""
    return place_from(unit.place_object_id, unit.place_unit_id)


def one_place(found: Iterable[Optional[Place]]) -> Optional[Place]:
    """**Der EINE Ort, an dem alle liegen** – oder ``None`` (verschiedene Orte, nirgends oder
    leer). Keine Antwort ist besser als eine erfundene: «40 in Regal A», obwohl zwölf auf der
    Werkbank liegen, wäre falsch."""
    seen = list(found)
    first = seen[0] if seen else None
    return first if first is not None and all(p == first for p in seen) else None


def stations_for(db: Session, object_ids: Iterable[int]) -> dict[int, Station]:
    """Objektnummern → Halter, in **drei** Abfragen statt einer je Nummer (gegen N+1).

    Eine Nummer, die zu nichts auflöst, fehlt im Ergebnis – die Anzeige zeigt dann die
    nackte Nummer.
    """
    ids = {int(o) for o in object_ids if o}
    if not ids:
        return {}
    out: dict[int, Station] = {}

    rows = (
        db.query(Instance.object_id, Article.name)
        .join(Article, Article.id == Instance.article_id)
        .filter(Instance.object_id.in_(ids))
        .all()
    )
    for object_id, article_name in rows:
        out[object_id] = Station(object_id, "instance", article_name or "Instanz")

    for user in db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all():
        out[user.object_id] = Station(user.object_id, "user", user.display_name)

    for co in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids)).all():
        out[co.object_id] = Station(co.object_id, "organization", sites.legal_name(co))

    return out


def unit_stations(db: Session, unit_ids: Iterable[int]) -> dict[int, Station]:
    """Träger-Stücke → Station, in **einer** Abfrage: Objektnummer der Instanz, Stück-Nummer
    als Beschriftung."""
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
            article_name or "Einzelinstanz",
            number=unit_number(instance, unit),
        )
        for unit, instance, article_name in rows
    }


def describe_all(db: Session, places: Iterable[Optional[Place]]) -> dict[Place, Station]:
    """Orte beider Arten → Stationen, batchweise je Art (gegen eine Abfrage je Ort)."""
    wanted = {p for p in places if p}
    objects = stations_for(db, [pid for kind, pid in wanted if kind == OBJECT])
    units = unit_stations(db, [pid for kind, pid in wanted if kind == UNIT])
    out: dict[Place, Station] = {}
    for place in wanted:
        kind, pid = place
        found = objects.get(pid) if kind == OBJECT else units.get(pid)
        if found is not None:
            out[place] = found
    return out


#: Wie viele Treffer eine Suche höchstens liefert.
SEARCH_LIMIT = 8


def search(db: Session, query: str, *, limit: int = SEARCH_LIMIT) -> list[Station]:
    """**Halter suchen — nach Nummer oder nach Namen.**

    «001» trifft die Objektnummer, «Clemens» die Person, «Regal» den Behälter. Gesucht wird
    nur, was Halter sein kann – dieselbe Menge, die ``station_of`` auflöst und
    ``assert_placeable`` durchlässt (keine Artikel, Aufträge oder Träger-Stücke).
    """
    q = (query or "").strip()
    if not q:
        return []
    out: list[Station] = []

    # Dieselbe Bedingung wie jedes Referenzfeld (``services/lookup``), je Halter-Art.
    rows = (
        db.query(Instance.object_id, Article.name)
        .join(Article, Article.id == Instance.article_id)
        .filter(lookup.matches(q, Instance.object_id, Article.name))
        .order_by(Instance.object_id.desc())
        .limit(limit)
        .all()
    )
    for object_id, article_name in rows:
        out.append(Station(object_id, "instance", article_name or "Instanz"))

    # Personen über die EINE Personensuche – dieselbe Bedingung wie jedes Personenfeld.
    out.extend(Station(u.object_id, "user", u.display_name)
               for u in people.search(db, q, limit=limit))

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
    out.extend(Station(c.object_id, "organization", sites.legal_name(c)) for c in companies)

    return out[:limit]


def station_of(db: Session, object_id: int) -> Optional[Station]:
    """Ein einzelner Halter — dieselbe Frage, andere Körnung."""
    return stations_for(db, [object_id]).get(int(object_id))


def describe(db: Session, place: Optional[Place]) -> Optional[Station]:
    """Ein Ort beider Arten → seine Station. Für Meldungen und Antworten."""
    return describe_all(db, [place]).get(place) if place else None


def chain(db: Session, place: Optional[Place]) -> list[Station]:
    """Die Kette von innen nach aussen: Getriebe › Behälter › Regal › Werk Nord.

    Sie endet an einem Halter mit Anschrift, wo nichts mehr liegt oder nichts mehr auflöst;
    leer heisst standortlos. Zyklensicher (gesehene Orte, Obergrenze).
    """
    if not place:
        return []
    return chains_for(db, [place]).get(place, [])


def _places_of_instances(db: Session, object_ids: list[int]) -> dict[int, Place]:
    """**Wo liegen diese Instanzen?** — eine Abfrage für alle.

    Eine Instanz als Halter liegt dort, wo alle ihre Stücke am selben Halter liegen
    (``one_place``); sonst endet die Kette – es wird keine Antwort erfunden. **Verschrottete
    Stücke zählen nicht**: sie haben keinen Ort mehr, und eine verschrottete Kiste in einer
    Charge darf die Kette der übrigen nicht abbrechen.
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
        .filter(Instance.object_id.in_(set(object_ids)),
                InstanceUnit.status.notin_(st.TERMINAL_UNIT_STATUSES))
        .distinct()
        .all()
    )
    found: dict[int, list[Optional[Place]]] = {}
    for object_id, place_object_id, place_unit_id in rows:
        found.setdefault(object_id, []).append(place_from(place_object_id, place_unit_id))
    return {o: p for o, ps in found.items() if (p := one_place(ps)) is not None}


def _places_of_units(db: Session, unit_ids: list[int]) -> dict[int, Place]:
    """**Wo liegen diese Träger-Stücke?** — die Fortsetzung der Kette über ein Stück."""
    if not unit_ids:
        return {}
    rows = (
        db.query(InstanceUnit.id, InstanceUnit.place_object_id, InstanceUnit.place_unit_id)
        .filter(InstanceUnit.id.in_(set(unit_ids)))
        .all()
    )
    return {unit_id: p for unit_id, po, pu in rows if (p := place_from(po, pu)) is not None}


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
    """Die Ketten **mehrerer** Halter — stufenweise, nicht je Halter einzeln (gegen N+1).

    Gleiche Halter teilen ihre Kette. Je Station kommt **beides** zurück: der Ort (zum
    Vergleichen) und die Station (zum Anzeigen).
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
        stations = describe_all(db, frontier)
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

    Das Ziel ist keines der Stücke und liegt nicht **in** einem von ihnen (kein Kreis).
    Verglichen werden Orte, nicht Objektnummern (Träger und Instanz teilen eine).
    """
    own: set[Place] = {(OBJECT, i.object_id) for i in _instances_of(db, units)}
    own |= {(UNIT, u.id) for u in units}
    if target in own:
        raise Invalid(f"«{label}» kann nicht in sich selbst liegen.")
    inside = {place for place, _ in _walk(db, [target]).get(target, [])}
    if own & inside:
        raise Invalid(f"«{label}» liegt selbst in dem, was bewegt werden soll – "
                    f"das ergäbe einen Ort, der im Kreis führt.")


def assert_placeable(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """Ein **gescanntes** Ziel prüfen: gibt es den Halter, und bildet er keinen Kreis?"""
    station = station_of(db, target)
    if station is None:
        raise NotFound(f"Die Objektnummer {target} gibt es nicht – ein Ziel muss ein Regal, "
                    f"eine Person oder ein Unternehmen sein.")
    _assert_placeable(db, units=units, target=(OBJECT, int(target)), label=station.label)
    return station


def _instances_of(db: Session, units: list[InstanceUnit]) -> list[Instance]:
    ids = {u.instance_id for u in units}
    return db.query(Instance).filter(Instance.id.in_(ids)).all() if ids else []


def place(db: Session, *, units: list[InstanceUnit], target: int) -> Station:
    """**Die eine Schreibstelle für einen gescannten Halter.** Prüft, dann setzt.

    Kein Status, keine Zugehörigkeit, kein Log – die Bewegung hält das Modul im Log fest
    (``process.confirm_step``).
    """
    station = assert_placeable(db, units=units, target=target)
    for unit in units:
        unit.place_object_id = int(target)
        unit.place_unit_id = None
    return station


def place_in(db: Session, *, units: list[InstanceUnit], carrier: InstanceUnit) -> None:
    """**Die eine Schreibstelle für einen Träger** — dieses Stück steckt jetzt in jenem.
    Nur vom Verbrauch gerufen (ein Träger hat kein Etikett)."""
    if not units:
        return
    _assert_placeable(
        db, units=units, target=(UNIT, carrier.id),
        label=f"Einzelinstanz {number_of(db, carrier)}",
    )
    for unit in units:
        unit.place_unit_id = carrier.id
        unit.place_object_id = None


def take_out(db: Session, units: list[InstanceUnit]) -> None:
    """**Ausbauen** – ein Stück, das in einem Träger steckt, liegt danach dort, wo der
    Träger liegt (gerufen, wenn ein Auftrag es greift, ``release.release``). Die
    Genealogie im Log bleibt."""
    inside = [u for u in units if u.place_unit_id]
    if not inside:
        return
    carriers = {
        c.id: c for c in db.query(InstanceUnit)
        .filter(InstanceUnit.id.in_({u.place_unit_id for u in inside})).all()
    }
    for unit in inside:
        carrier = carriers[unit.place_unit_id]
        unit.place_unit_id = carrier.place_unit_id
        unit.place_object_id = carrier.place_object_id


def forget(db: Session, units: list[InstanceUnit]) -> None:
    """**Der Ort gilt nicht mehr** — die zweite Form von ``place``, für ein Stück, das zur
    Historie wird (``Status.stock``)."""
    for unit in units:
        unit.place_object_id = None
        unit.place_unit_id = None


def apply_for_step(
    db: Session, *, step: ProcessStep, units: list[InstanceUnit],
    target: Optional[int],
) -> dict[int, dict[str, object]]:
    """**Was dieses Modul am Ort ändert** — leer, wenn es nichts bewegt.

    ``process.confirm_step`` ruft das für jedes Modul (wie ``consumption.plan``). Zurück
    kommt je Stück Herkunft und Ziel – als Payload in den Log (§7.2).
    """
    goal = modules.get(step.module_type).movement_for(step.config, target=target)
    if goal is None:
        return {}
    # Erst lesen, dann schreiben: die Herkunft (Halter oder Träger, darum ``Place``).
    before = {u.id: place_of(u) for u in units}
    station = place(db, units=units, target=goal)
    return {
        u.id: {
            "place": {"from": before[u.id], "to": goal, "label": station.label},
        }
        for u in units
    }


# ---------------------------------------------------------------------------
# Lesen — für Anzeige und für die Ortsprüfung eines Moduls
# ---------------------------------------------------------------------------

def for_units(db: Session, units: Iterable[InstanceUnit]) -> dict[int, list[Station]]:
    """Je Einzelinstanz ihre Kette — aufgelöst **je Halter**, nicht je Stück (gegen N+1)."""
    at = {u.id: place_of(u) for u in units}
    chains = chains_for(db, [p for p in at.values() if p])
    return {uid: chains.get(p, []) for uid, p in at.items() if p}


def common_holder(units: Iterable[InstanceUnit]) -> Optional[Place]:
    """**Der Ort, an dem ALLE liegen** — oder ``None`` (verschiedene Orte oder nirgends:
    dann wird kein Ort verlangt)."""
    return one_place(place_of(u) for u in units)


def within(db: Session, places: Iterable[Optional[Place]], holder: Place) -> set[Place]:
    """**Welche dieser Orte liegen an (oder in) diesem Halter?** «Am Ort» heisst: der Halter
    steht in der **Kette** des Ortes – eine Kette je Ort."""
    walked = _walk(db, [p for p in places if p])
    return {
        head for head, row in walked.items()
        if head == holder or any(place == holder for place, _ in row)
    }

