"""**Was ein Verbrauchsmodul braucht, und woher es das nimmt.**

Die Rechnung ist eine Zeile: *Menge je Stück × Stücke, die davorstehen*. Sie steht hier
und nicht in der Definition, weil sie beim **Erreichen** des Moduls fällig ist – vorher
weiss niemand, wie viele Produkte ankommen (§1). Eine Vorlage, die eine Auftragsmenge
nennt, ist bei der zweiten Menge falsch.

**Dieses Modul schreibt nichts.** Es plant: es sagt, was fehlt, und es sagt, welche
Stücke genommen würden. Geschrieben wird an der einen Stelle, an der jeder Statuswechsel
geschrieben wird (``process._enter_at_step`` / ``process._pass``) – ein zweiter
Schreibweg wäre genau das, was es hier nicht geben darf.

**Genommen wird nur, was frei ist** – Zustand ``Freigegeben`` und keine offene
Zugehörigkeit. Das ist keine zusätzliche Regel, sondern dieselbe, aus der auch
``deviation_flags`` liest: wer am Regelstart steht, war regulär verfügbar. Damit macht
ein Verbrauch einen Auftrag nie stillschweigend zur Abweichung, und ein gesperrtes Stück
kann nicht versehentlich verbaut werden.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from ..models import Article, Instance, InstanceUnit, OrderUnit, ProcessStep
from . import places


@dataclass
class Source:
    """Eine Instanz, aus der genommen werden könnte — und wie viel dort frei liegt."""

    instance_object_id: int
    free: int
    #: **Davon am Arbeitsort.** Ohne diese Zahl müsste die Oberfläche raten, aus welcher
    #: Kiste genommen werden kann – und «am Ort» ist eine Aussage über die *Kette*, die
    #: sie gar nicht auflösen kann. Ohne Ortsanforderung gleich ``free``.
    here: int = 0
    #: **Wo diese Kiste liegt.** Die Antwort auf «warum sind sie nicht hier» – ohne sie
    #: nennt die Zeile eine Zahl und verschweigt den Grund.
    place: Optional[places.Place] = None


@dataclass
class Need:
    """Eine Zeile der Stückliste, gegen die Wirklichkeit gehalten.

    ``required`` ist die Rechnung dieses Augenblicks (Menge je Stück × wartende Stücke),
    ``available`` der freie Bestand. Fehlt etwas, ist das **kein Zustand des Auftrags** –
    das Modul ist schlicht nicht fertig, und es sagt in Klartext, woran es liegt (§4).
    """

    article_object_id: int
    article_name: str
    per_unit: int
    required: int
    available: int
    #: **Davon am Arbeitsort** – frei *und* dort, wo das Produkt liegt. Ohne
    #: Ortsanforderung (``place is None``) ist es dasselbe wie ``available``.
    here: int = 0
    #: **Wo das Material liegen muss** – abgeleitet aus dem Ort des Produkts, nicht
    #: konfiguriert. ``None`` heisst: dieses Modul verlangt keinen Ort.
    place: Optional[places.Place] = None
    sources: list[Source] = field(default_factory=list)

    @property
    def missing(self) -> int:
        """Was an Menge fehlt – unabhängig davon, wo es liegt."""
        return max(0, self.required - self.available)

    @property
    def misplaced(self) -> int:
        """Was da ist, aber **nicht hier**. Der Fall, den ein Transport löst."""
        return max(0, min(self.required, self.available) - self.here)


def _free(db: Session, article_object_id: int, *,
          instances: Optional[list[int]] = None,
          at: Optional[places.Place] = None) -> list[tuple[InstanceUnit, Instance]]:
    """Die **freien** Stücke eines Artikels — FIFO, älteste Nummer zuerst.

    Frei heisst zweierlei: am Regelstart (``Freigegeben``) **und** ohne offene
    Zugehörigkeit. *Die zweite Hälfte ist heute ein Gurt neben dem Hosenträger* – wer in
    einem Auftrag läuft, steht auf ``Im Prozess``, also greift bereits die erste. Sie
    bleibt trotzdem stehen, weil sie nichts kostet und die Aussage «frei» vollständig
    macht: ein Stück, dessen Zustand von aussen verstellt wurde, ist damit trotzdem
    nicht greifbar.

    Die Instanz kommt mit, weil die beiden Fragen dieselbe Abfrage teilen: «wie viele sind
    frei» und «aus welchen Kisten». Zweimal gefragt wären es zwei Abfragen je Artikel und
    eine Antwort, die auseinanderlaufen kann.

    ``instances`` schränkt auf die genannten Instanzen ein und **hält deren Reihenfolge**:
    wer eine andere Instanz wählt, hat damit auch gesagt, welche zuerst.

    ``at`` schränkt auf einen **Ort** ein: nur was dort (oder darin) liegt. Gefiltert wird
    **nach** der Abfrage, nicht in ihr – «am Ort» ist eine Aussage über die *Kette*
    (die Schraube in der Kiste auf Werkbank 5 ist auf Werkbank 5), und die löst
    ``places.at_holder`` batchweise auf.
    """
    rows = (
        db.query(InstanceUnit, Instance)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .join(Article, Article.id == Instance.article_id)
        .outerjoin(
            OrderUnit,
            (OrderUnit.instance_unit_id == InstanceUnit.id)
            & (OrderUnit.released_at.is_(None)),
        )
        .filter(
            Article.object_id == article_object_id,
            InstanceUnit.is_active.is_(True),
            Instance.is_active.is_(True),
            InstanceUnit.status == st.START_BEFORE,
            OrderUnit.id.is_(None),
        )
        .order_by(InstanceUnit.id)
        .all()
    )
    if instances is not None:
        rank = {nr: pos for pos, nr in enumerate(instances)}
        rows = [(u, i) for u, i in rows if i.object_id in rank]
        rows.sort(key=lambda pair: (rank[pair[1].object_id], pair[0].id))
    if at is not None:
        here = places.at_holder(db, [u for u, _ in rows], at)
        rows = [(u, i) for u, i in rows if u.id in here]
    return list(rows)


def _one_place(found: list[Optional[places.Place]]) -> Optional[places.Place]:
    """Der Ort einer Kiste – **nur wenn ihre freien Stücke an EINEM liegen.**

    Der Ort hängt am Stück, nicht an der Gruppe (§9.8): eine Charge darf verteilt sein.
    Den des ersten Stücks zu nennen wäre die bequeme Antwort und bei einer verteilten
    Charge schlicht falsch – «40 in Regal A», obwohl zwölf längst auf der Werkbank
    liegen. Dieselbe Regel wie ``places.common_holder``: keine Antwort ist besser als
    eine erfundene; die **Zahl** daneben (``here``) bleibt in jedem Fall exakt.
    """
    first = found[0] if found else None
    return first if first is not None and all(p == first for p in found) else None


def required_place(step: ProcessStep,
                   products: list[InstanceUnit]) -> Optional[places.Place]:
    """**Wo muss das Material dieses Moduls liegen?** — die eine Ableitung.

    Der Modultyp deklariert die Frage (``Module.material_place``), beantwortet wird sie
    aus dem **Ort der Produkte**: die Komponenten müssen dorthin, wo verbaut wird. Ein
    eigenes Ortsfeld am Modul wäre eine zweite Ortsangabe, und zwei können sich
    widersprechen.

    **Wo nichts steht, wird nichts verlangt.** Liegen die Produkte nirgends – oder an
    *verschiedenen* Orten – gibt es keine Anforderung: eine erfundene sperrte das Modul
    auf einen Ort, den nur ein Teil der Stücke teilt. Das ist zugleich der Grund, warum
    diese Änderung keinen bestehenden Ablauf anhält: ohne Ort am Produkt ändert sich
    nichts.
    """
    if modules.get(step.module_type).material_place != modules.AT_PRODUCT:
        return None
    return places.common_holder(products)


def needs(db: Session, step: ProcessStep, *,
          products: list[InstanceUnit]) -> list[Need]:
    """**Was braucht dieses Modul jetzt — und ist es da?**

    ``products`` sind die Produkt-Stücke, für die gerechnet wird. Am Modul ist das alles,
    was davorsteht; in einem einzelnen Vorgang sind es die Stücke der einen verifizierten
    Instanz. Dieselbe Rechnung, anderer Ausschnitt – zwei Formeln wären zwei Antworten
    auf eine Frage.

    Sie kommen als **Stücke** und nicht als Zahl, weil neben der Menge auch der **Ort**
    daraus folgt: wo verbaut wird, ist der Ort der Produkte.

    Ein Modul ohne Stückliste gibt eine leere Liste zurück; die Aufrufstelle braucht
    darum keine Fallunterscheidung nach dem Modultyp.
    """
    rows = modules.lines_of(step.config)
    if not rows:
        return []
    names = {
        a.object_id: a.name
        for a in db.query(Article)
        .filter(Article.object_id.in_([r["article"] for r in rows]))
        .all()
    }
    where = required_place(step, products)
    out: list[Need] = []
    for row in rows:
        free = _free(db, row["article"])
        units = [u for u, _ in free]
        # **Zwei Zahlen, eine Abfrage.** «Verfügbar» und «hier» sind dieselbe Menge,
        # einmal ungefiltert und einmal auf den Arbeitsort eingeschränkt; getrennt geholt
        # wären es zwei Stände desselben Bestands.
        here = places.at_holder(db, units, where) if where else {u.id for u in units}
        by_instance: dict[int, int] = {}
        here_instance: dict[int, int] = {}
        at_instance: dict[int, list[Optional[places.Place]]] = {}
        for unit, instance in free:
            by_instance[instance.object_id] = by_instance.get(instance.object_id, 0) + 1
            if unit.id in here:
                here_instance[instance.object_id] = \
                    here_instance.get(instance.object_id, 0) + 1
            at_instance.setdefault(instance.object_id, []).append(places.place_of(unit))
        out.append(Need(
            article_object_id=row["article"],
            article_name=names.get(row["article"], f"Artikel {row['article']}"),
            per_unit=row["quantity"],
            required=row["quantity"] * len(products),
            available=len(free),
            here=len(here),
            place=where,
            sources=[Source(instance_object_id=nr, free=n,
                            here=here_instance.get(nr, 0),
                            place=_one_place(at_instance.get(nr, [])))
                     for nr, n in sorted(by_instance.items())],
        ))
    return out


def plan(db: Session, *, step: ProcessStep, products: list[InstanceUnit],
         sources: Optional[list[int]] = None) -> dict[int, list[InstanceUnit]]:
    """**Welches Stück kommt in welches Produkt?** — ``{Produkt-Stück: [Komponenten]}``.

    Zugeteilt wird **je Produkt-Stück** (§3): das ist die Körnung, in der die Genealogie
    später gelesen wird, und sie entsteht hier, nicht hinterher aus einer Vermutung.
    Welche Schraube in welches Getriebe geht, ist dabei keine menschliche Entscheidung –
    Schrauben desselben Artikels sind austauschbar. Entscheidend ist, dass die Zuordnung
    **aufgeschrieben** wird; darum ist sie hier deterministisch (FIFO) statt geraten.

    ``sources`` sind die Instanzen, die der Mensch gewählt bzw. gescannt hat. Ohne sie
    gilt der ganze freie Bestand des Artikels. Es ist **keine Vorgabe von Mengen**: wie
    viel gebraucht wird, sagt die Stückliste, und ein zweiter Weg, das zu bestimmen, wäre
    ein zweiter Massstab.

    Reicht es nicht, ist das ein Fehler mit Namen und Zahlen – **bevor** irgendetwas
    geschrieben ist. Ein Modul, das die Hälfte verbaut und dann abbricht, hinterlässt
    einen Zustand, den niemand gewollt hat.

    **Und «reichen» heisst: hier.** Genommen wird nur, was am Arbeitsort liegt
    (``required_place``) – das ist die Schreibform derselben Regel, die ``needs`` als
    Auskunft zeigt. Zwei Formen, ein Massstab; ein milderer hier wäre eine Zeile, die
    «0 hier» meldet, und ein Modul, das trotzdem verbaut.
    """
    rows = modules.lines_of(step.config)
    if not rows:
        if sources:
            raise HTTPException(
                status_code=400,
                detail=(f"«{modules.label(step.module_type)}» verbaut nichts – "
                        f"hier ist keine Komponente zu wählen."),
            )
        return {}
    if not products:
        return {}

    names = {
        a.object_id: a.name
        for a in db.query(Article)
        .filter(Article.object_id.in_([r["article"] for r in rows]))
        .all()
    }
    where = required_place(step, products)
    out: dict[int, list[InstanceUnit]] = {p.id: [] for p in products}
    for row in rows:
        need = row["quantity"] * len(products)
        free = [u for u, _ in _free(db, row["article"], instances=sources or None,
                                    at=where)]
        if len(free) < need:
            name = names.get(row["article"], f"Artikel {row['article']}")
            # **Der Grund gehört in die Meldung.** «3 verfügbar» ist wahr und nutzlos,
            # wenn 40 im Regal liegen und nur der Ort nicht stimmt – dann ist die
            # Handlung ein Transport und nicht eine Beschaffung.
            elsewhere = len([u for u, _ in _free(db, row["article"],
                                                 instances=sources or None)]) - len(free)
            here = places.describe(db, where) if where else None
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{name} ({row['article']}): gebraucht werden {need} Stück "
                    f"({row['quantity']} je Einzelinstanz × {len(products)}), "
                    f"verfügbar sind {len(free)}"
                    + (f" bei «{here.label}»" if here else "")
                    + (f" – {elsewhere} liegen woanders." if elsewhere else
                       (" – und zwar nur aus den gewählten Instanzen." if sources else "."))
                ),
            )
        # **Der Reihe nach, Produkt für Produkt.** Nicht rundum verteilt: ein Getriebe
        # bekommt seine vier Schrauben, dann das nächste. Das ist die Reihenfolge, in der
        # gearbeitet wird, und darum die, die im Nachweis stehen soll.
        pos = 0
        for product in products:
            out[product.id].extend(free[pos:pos + row["quantity"]])
            pos += row["quantity"]
    return out


def payloads(assignment: dict[int, list[InstanceUnit]],
             *, verification: Optional[str]) -> dict[int, dict[str, Any]]:
    """Je Komponente ihr Log-Eintrag: **worin sie verbaut wurde**.

    Das ist die ganze Genealogie-Mechanik – kein Feld am Datensatz, keine Tabelle, keine
    Beziehung. Der Log hält fest, was passiert ist, und was passiert ist, war «dieses
    Stück ging in jenes». Eine Spalte ``into_instance_id`` wäre eine zweite Wahrheit
    daneben, die bei einer Demontage rückwirkend gelöscht würde.
    """
    return {
        component.id: {"into": product_id, "verification": verification}
        for product_id, components in assignment.items()
        for component in components
    }
