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


@dataclass
class Source:
    """Eine Instanz, aus der genommen werden könnte — und wie viel dort frei liegt."""

    instance_object_id: int
    free: int


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
    sources: list[Source] = field(default_factory=list)

    @property
    def missing(self) -> int:
        return max(0, self.required - self.available)


def _free(db: Session, article_object_id: int, *,
          instances: Optional[list[int]] = None) -> list[tuple[InstanceUnit, Instance]]:
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
    if instances is None:
        return list(rows)
    rank = {nr: pos for pos, nr in enumerate(instances)}
    chosen = [(u, i) for u, i in rows if i.object_id in rank]
    chosen.sort(key=lambda pair: (rank[pair[1].object_id], pair[0].id))
    return chosen


def needs(db: Session, step: ProcessStep, *, pieces: int) -> list[Need]:
    """**Was braucht dieses Modul jetzt — und ist es da?**

    ``pieces`` ist die Zahl der Produkt-Stücke, für die gerechnet wird. Am Modul ist das
    alles, was davorsteht; in einem einzelnen Vorgang sind es die Stücke der einen
    verifizierten Instanz. Dieselbe Rechnung, anderer Ausschnitt – zwei Formeln wären
    zwei Antworten auf eine Frage.

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
    out: list[Need] = []
    for row in rows:
        free = _free(db, row["article"])
        by_instance: dict[int, int] = {}
        for _, instance in free:
            by_instance[instance.object_id] = by_instance.get(instance.object_id, 0) + 1
        out.append(Need(
            article_object_id=row["article"],
            article_name=names.get(row["article"], f"Artikel {row['article']}"),
            per_unit=row["quantity"],
            required=row["quantity"] * pieces,
            available=len(free),
            sources=[Source(instance_object_id=nr, free=n)
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
    out: dict[int, list[InstanceUnit]] = {p.id: [] for p in products}
    for row in rows:
        need = row["quantity"] * len(products)
        free = [u for u, _ in _free(db, row["article"], instances=sources or None)]
        if len(free) < need:
            name = names.get(row["article"], f"Artikel {row['article']}")
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{name} ({row['article']}): gebraucht werden {need} Stück "
                    f"({row['quantity']} je Einzelinstanz × {len(products)}), "
                    f"verfügbar sind {len(free)}"
                    + (" – und zwar nur aus den gewählten Instanzen."
                       if sources else ".")
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
