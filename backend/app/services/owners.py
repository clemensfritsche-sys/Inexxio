"""**Wem ein Stück gehört** — ein Zeiger, kein Zustand.

Der Zwilling von ``services/places``. Dort steht, **wo** eine Einzelinstanz liegt; hier,
**wem** sie gehört. Zwei Fragen, zwei Spalten, und sie bedingen einander nicht:

===================  =========================  =================================
                     liegt bei uns              liegt beim Partner
===================  =========================  =================================
**gehört uns**       Lager                      Muster · Leihgabe · Konsignation
**gehört ihm**       Beistellung                verkauft
===================  =========================  =================================

Alle vier Felder kommen im Alltag eines Maschinenbauers vor – und keines davon lässt sich
mit einer Angabe allein ausdrücken. Genau daran scheitert der naheliegende Weg, «Verkauft»
als **Status** zu führen: der Status ist die Prozess-Achse, und solange ein Auftrag läuft,
steht dort ``Im Prozess``. Völlig zu Recht – nur schreibt der Prozess bei jedem Modul, und
das Geschäft einmal. Ein Feld mit zwei Chefs verliert immer gegen den, der öfter schreibt.

**Darum ein Zeiger.** Er ändert nie einen Status, nie eine Zugehörigkeit, nie den Ort.
Daraus folgt die Robustheit ohne eine einzige Prüfung: **keine andere Regel im System muss
von ihm wissen** – dieselbe Begründung, mit der der Ort gebaut wurde.

**``NULL`` heisst «uns»**, und das ist ein regulärer Zustand: alles, was wir erzeugen,
gehört uns, bis jemand es verkauft. Kein Backfill, keine Wanderung – die Spalte kommt
leer und bedeutet dabei genau das Richtige.

**Wer besitzen kann, ist wer eine Anschrift trägt.** Ein Benutzer (natürliche Person) oder
ein Unternehmen (juristische Person) – mehr gibt es rechtlich nicht. Das ist buchstäblich
dieselbe Menge, die ``places.ADDRESS_HOLDERS`` führt, und sie wird darum **geteilt** statt
nachgebaut: eine Instanz kann Halter sein (ein Regal hält Schrauben), besitzen kann sie
nichts.

**Keine Zyklen.** Die einzige Regel des sonst dummen Ortsfeldes entfällt hier ersatzlos:
ein Eigentümer ist nie wieder ein Stück, also kann keine Kette im Kreis laufen. Was es
nicht gibt, braucht kein Netz.

**Und «gehört uns» ist nicht dasselbe wie ``NULL``.** Kaufen zwei unserer Gesellschaften
Material, gehört jedes Stück *einer* von beiden – das ist die Frage «womit kann ich als
jeweiliges Unternehmen wirtschaften», und sie wird von **demselben** Zeiger beantwortet:
er trägt dann die Objektnummer der Gesellschaft. Eine zweite Spalte «ist das unseres»
wäre die zweite Wahrheit, die bei der ersten Umfirmierung auseinanderläuft.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CompanySettings, InstanceUnit
from . import places

#: **Wer Eigentümer sein darf.** Dieselbe Menge, die eine Anschrift trägt – und das ist
#: keine Analogie, sondern derselbe Sachverhalt: wer adressierbar ist, ist eine
#: Rechtsperson, und nur eine Rechtsperson besitzt.
OWNERS = places.ADDRESS_HOLDERS

#: Wie «uns» heisst, wo ein Wort gebraucht wird. Ein Eigentümer ohne Nummer ist nicht
#: «unbekannt» – er ist das Haus.
US = "Uns"


@dataclass(frozen=True)
class Transfer:
    """**Ein Eigentumsübergang, wie ein Modul ihn erklärt.**

    ``to`` ist die Objektnummer des neuen Eigentümers – oder ``None`` für «uns». Genau
    deshalb gibt es diese Klasse und nicht bloss ein ``Optional[int]``: ``None`` müsste
    sonst zwei Dinge heissen, «kein Wechsel» und «an uns», und die Stelle, an der jemand
    das verwechselt, verschenkt stillschweigend Eigentum.
    """

    to: Optional[int]


def owner_of(unit: InstanceUnit) -> Optional[int]:
    """**Wem gehört dieses Stück?** – die eine Lesestelle. ``None`` heisst «uns»."""
    return int(unit.owner_object_id) if unit.owner_object_id else None


# ---------------------------------------------------------------------------
# Gehört es uns? — eine Frage, zwei Formen
# ---------------------------------------------------------------------------

def ours(db: Session) -> set[int]:
    """**Die Objektnummern unserer Gesellschaften** – in EINER Abfrage.

    Sie steht hier als Menge und nicht als Prüfung je Stück: eine Bestandsansicht fragt
    für sechzig Zeilen dasselbe, und je Zeile aufgelöst wären es sechzig Abfragen – die
    N+1-Falle, an der die Ortsanzeige des Vorgängersystems hing.
    """
    rows = (
        db.query(CompanySettings.object_id)
        .filter(CompanySettings.object_id.isnot(None),
                CompanySettings.is_active.is_(True))
        .all()
    )
    return {int(o) for (o,) in rows if o}


def is_ours(db: Session, owner_id: Optional[int]) -> bool:
    """**Gehört ein Stück mit diesem Eigentümer uns?** – die zweite Form derselben Regel.

    ``None`` ist unseres (das Haus), und eine unserer Gesellschaften ebenso. Zwei Formen
    einer Regel sind in Ordnung; zwei Regeln nicht – darum liest diese Funktion dieselbe
    Menge und formuliert die Frage nicht ein zweites Mal.
    """
    return owner_id is None or int(owner_id) in ours(db)


def names_for(db: Session, owner_ids: Iterable[Optional[int]]) -> dict[int, str]:
    """Objektnummern → Name der Rechtsperson, batchweise.

    **Geteilt mit dem Ort** (``places.stations_for``): «wie heisst die Nummer 100000512»
    ist dieselbe Frage, egal ob sie etwas hält oder etwas besitzt. Eine eigene Auflösung
    daneben wäre die Stelle, an der ein Unternehmen hier seine Rechtsform verliert und
    dort nicht.

    Eine Nummer, die zu nichts auflöst, fehlt im Ergebnis – das ist eine Antwort, kein
    Fehler: die Anzeige zeigt dann die nackte Nummer, statt zu verschwinden.
    """
    ids = {int(o) for o in owner_ids if o}
    if not ids:
        return {}
    return {
        object_id: station.label
        for object_id, station in places.stations_for(db, ids).items()
        if station.kind in OWNERS
    }


# ---------------------------------------------------------------------------
# Schreiben — genau hier, sonst nirgends
# ---------------------------------------------------------------------------

def assert_ownable(db: Session, target: Optional[int]) -> Optional[str]:
    """**Darf diese Nummer besitzen?** – die Prüfung vor jedem Schreiben.

    ``None`` geht immer durch: «uns» ist keine Nummer, die man nachschlagen müsste.

    Abgewiesen wird alles, was **keine Rechtsperson** ist – eine Instanz zum Beispiel:
    ein Regal hält Schrauben, es besitzt sie nicht. Streng schreiben, tolerant lesen.
    """
    if target is None:
        return None
    station = places.station_of(db, int(target))
    if station is None or station.kind not in OWNERS:
        raise HTTPException(
            status_code=400,
            detail=(f"Die Objektnummer {target} kann nichts besitzen – ein Eigentümer "
                    f"ist eine Person oder ein Unternehmen."),
        )
    return station.label


def transfer(db: Session, *, units: list[InstanceUnit],
             to: Optional[int]) -> Optional[str]:
    """►►► **Die EINE Schreibstelle für den Eigentümer.** ◄◄◄ Prüft, dann setzt.

    Kein Statuswechsel, kein Ortswechsel, kein eigener Log-Eintrag: **dass** ein Stück den
    Eigentümer gewechselt hat, hält der Ereignis-Log an seinem Modul fest
    (``process.confirm_step`` schreibt es in die Nutzlast des ``step``-Ereignisses), und
    dort steht es mit Herkunft und Ziel. Ein zweiter Eintrag hier wäre eine zweite
    Wahrheit über denselben Vorgang – genau die Begründung, aus der auch ``places.place``
    nichts protokolliert.

    Zurück kommt der **Name** des neuen Eigentümers (``None`` für «uns»), damit der
    Aufrufer ihn in den Log schreiben kann, ohne ihn ein zweites Mal nachzuschlagen: ein
    Name im Log ist eingefroren und überlebt eine spätere Umfirmierung.
    """
    label = assert_ownable(db, to)
    for unit in units:
        unit.owner_object_id = int(to) if to else None
    return label


def apply_for_step(db: Session, *, units: list[InstanceUnit],
                   move: Optional[Transfer]) -> dict[int, dict[str, object]]:
    """**Was dieses Modul am Eigentum ändert** – und nichts, wenn es keines ist, das es
    ändert.

    Dieselbe Bauart wie ``places.apply_for_step``: die Ausführungsstelle ruft es für
    **jedes** Modul auf und fragt nicht nach dem Typ; die Antwort ist leer, wo nichts zu
    übertragen ist.

    ``move`` kommt vom Fach-Dienst, der die Frage beantworten **kann** – beim Beleg ist
    das ``voucher.transfer_for``, denn nur der kennt die Gegenpartei. Diese Funktion
    kennt kein Zahlungsmodul und soll keines kennen: sie schreibt einen Zeiger.

    Zurück kommt, **was passiert ist** – je Stück Herkunft und Ziel. Das reist als Payload
    in den Ereignis-Log, und damit steht der Eigentumsübergang dort, wo die Historie
    ohnehin steht (§7.2), statt in einer zweiten Tabelle daneben.
    """
    if move is None or not units:
        return {}
    # **Erst lesen, dann schreiben**: die Herkunft gibt es nach dem Setzen nicht mehr.
    before = {u.id: owner_of(u) for u in units}
    label = transfer(db, units=units, to=move.to)
    return {
        u.id: {"owner": {"from": before[u.id], "to": move.to, "label": label or US}}
        for u in units
    }


# ---------------------------------------------------------------------------
# Lesen — für die Bestandsansicht
# ---------------------------------------------------------------------------

def shares(db: Session, counts: dict[Optional[int], int]) -> list[dict[str, object]]:
    """**Gezählte Eigentümer → Segmente**: Nummer, Name, «unseres?», Menge.

    Die eine Umwandlung – Zwilling von ``schemas.instance.stock_states``. Sie steht hier
    und nicht im Schema, weil sie **fragen** muss (wie heisst die Nummer, gehört sie uns);
    ein Schema kennt keine Datenbank.

    ►►► **Eine Liste mit genau einem Eintrag ist keine Aussage.** ◄◄◄ Gehört alles uns,
    kommt sie **leer** zurück: ein einziges Segment «Uns 20» über einer Leiste, die
    ohnehin die Gesamtmenge zeigt, sagt nichts und kostet eine Zeile. Dieselbe Regel wie
    bei den Zuständen – was es nicht zu unterscheiden gibt, steht nicht da.

    **Uns zuerst, der Rest nach Menge** – nicht alphabetisch: wer am meisten hält, ist
    die Antwort auf «wem gehört das Zeug hier», und unsere eigene Seite ist der
    Bezugspunkt, vor dem man die fremde liest.
    """
    live = {o: n for o, n in counts.items() if n}
    if len(live) < 2:
        return []
    mine = ours(db)
    names = names_for(db, live)
    rows = [
        {
            "owner_object_id": owner,
            "name": US if owner is None else names.get(owner, str(owner)),
            "ours": owner is None or owner in mine,
            "quantity": n,
        }
        for owner, n in live.items()
    ]
    return sorted(rows, key=lambda r: (not r["ours"], -int(r["quantity"])))


def counts_for_article(db: Session, *, article_id: int) -> dict[Optional[int], int]:
    """**Wem gehören die Stücke dieses Artikels?** – Eigentümer → Anzahl, EINE Abfrage.

    Derselbe Umfang wie ``instances.article_states``: alle aktiven Einzelinstanzen des
    Artikels. Das ist kein Zufall, sondern die Bedingung dafür, dass die beiden Leisten
    der Bestandsansicht sich auf **dieselbe** Gesamtzahl summieren – zwei Aufteilungen
    einer Menge, nicht zwei Auskünfte über zwei Dinge.
    """
    from ..models import Instance  # lokal: sonst importiert dieses Modul den halben Bestand

    rows = (
        db.query(InstanceUnit.owner_object_id, func.count(InstanceUnit.id))
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .filter(
            Instance.article_id == article_id,
            Instance.is_active.is_(True),
            InstanceUnit.is_active.is_(True),
        )
        .group_by(InstanceUnit.owner_object_id)
        .all()
    )
    return {(int(o) if o else None): int(n) for o, n in rows}


def counts_for_instance(db: Session, *, instance_id: int) -> dict[Optional[int], int]:
    """Dieselbe Frage, eine Ebene tiefer – Eigentümer → Anzahl innerhalb EINER Instanz.

    Zwei Funktionen und keine mit einem Umschalter: die beiden Umfänge der
    Bestandsansicht sind zwei verschiedene Abfragen (die eine geht über die Instanzen des
    Artikels, die andere gar nicht), und ein Parameter dazwischen wäre ein ``if`` in einer
    Funktion, die eine Zahl liefern soll.
    """
    rows = (
        db.query(InstanceUnit.owner_object_id, func.count(InstanceUnit.id))
        .filter(InstanceUnit.instance_id == instance_id,
                InstanceUnit.is_active.is_(True))
        .group_by(InstanceUnit.owner_object_id)
        .all()
    )
    return {(int(o) if o else None): int(n) for o, n in rows}
