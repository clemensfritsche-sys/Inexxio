"""Aus einer Definitionszeile werden Einzelinstanzen.

Zwei Dinge stehen hier, und beide gehören zusammen: **wie viele Datensätze** eine Menge
ergibt (``plan``) und **dass es danach genau so viele sind** (``assert_quantity``).

Der Grundsatz aus dem Auftrag: *Neue Einzelinstanznummern entstehen ausschliesslich beim
Freigeben eines Auftrags, und ausschliesslich für Definitionszeilen mit der Herkunft
«Neu».* Dieses Modul ist der Weg dorthin; es hat genau einen Aufrufer
(``services/process.release``).
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, InstanceUnit
from ..models.instance import KINDS
from .instances import create_instances

#: Serialisierung des Artikels → wie die Menge auf Datensätze fällt.
#:
#:   ``unit``  – Einzelserialisierung: jedes Stück ist ein eigener Datensatz
#:   ``batch`` – Charge: ein Datensatz trägt alle Stücke
UNIT = "unit"
BATCH = "batch"

#: ``Article.serialization`` → ``Instance.kind``. Zwei Vokabulare für dieselbe Achse
#: (historisch gewachsen); die Übersetzung steht hier einmal, damit sie nicht an jeder
#: Aufrufstelle neu erfunden wird.
_KIND = {UNIT: "einzeln", BATCH: "batch"}


def plan(serialization: str, quantity: int) -> tuple[int, int]:
    """Menge → ``(Anzahl Instanzen, Einzelinstanzen je Instanz)``.

    **Hier und nur hier** steht der Unterschied zwischen den beiden Fällen — und er ist
    ein Zahlenpaar, kein zweiter Codepfad::

        Einzelserialisierung, Menge 3  →  (3, 1)   drei Instanzen, je eine  ``…-1``
        Charge, Menge 3                →  (1, 3)   eine Instanz, ``-1`` ``-2`` ``-3``

    In beiden Fällen ist das Produkt die Menge. Das ist keine Nebenbemerkung, sondern
    die Invariante, die ``assert_quantity`` gleich darauf prüft.
    """
    if serialization not in _KIND:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unbekannte Serialisierung «{serialization}» – erlaubt sind "
                f"{', '.join(_KIND)}. Ohne sie ist nicht entscheidbar, wie viele "
                f"Instanzen entstehen."
            ),
        )
    if quantity < 1:
        raise HTTPException(
            status_code=400,
            detail="Die Menge muss mindestens 1 sein – eine Zeile ohne Stück erzeugt nichts.",
        )
    if serialization == BATCH:
        return 1, quantity
    return quantity, 1


def kind_for(serialization: str) -> str:
    """``Instance.kind`` zur Serialisierung des Artikels."""
    if serialization not in _KIND:
        raise HTTPException(
            status_code=400, detail=f"Unbekannte Serialisierung «{serialization}».",
        )
    kind = _KIND[serialization]
    if kind not in KINDS:  # pragma: no cover – hält die beiden Vokabulare zusammen
        raise HTTPException(status_code=500, detail=f"Instanz-Typ «{kind}» gibt es nicht.")
    return kind


def create_for_line(db: Session, *, article: Article, quantity: int) -> list[InstanceUnit]:
    """Die Einzelinstanzen einer ``Neu``-Zeile erzeugen und zurückgeben.

    Reihenfolge der Rückgabe ist die Nummernreihenfolge (Instanz aufsteigend, Suffix
    aufsteigend) – damit die Zuordnung «Zeile → Stücke» stabil und nachvollziehbar ist.
    """
    instance_count, units_each = plan(article.serialization, quantity)
    instances = create_instances(
        db,
        article=article,
        kind=kind_for(article.serialization),
        instance_count=instance_count,
        units_each=units_each,
    )
    db.flush()
    ids = [i.id for i in instances]
    return (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id.in_(ids))
        .order_by(InstanceUnit.instance_id, InstanceUnit.suffix)
        .all()
    )


# ---------------------------------------------------------------------------
# ►► DIE MENGEN-INVARIANTE – EINE STELLE ◄◄
# ---------------------------------------------------------------------------

def assert_quantity(counts: list[tuple[int, int, str]], *, code: int) -> None:
    """Menge N heisst: **danach laufen exakt N Einzelinstanzen** im Prozess.

    ``counts`` ist je Definitionszeile ``(Soll, Ist, Bezeichnung)``. Eine Abweichung ist
    ein **harter Fehler**, der die Freigabe-Transaktion abbricht – nicht eine Warnung und
    schon gar keine stille Korrektur: eine Zeile, die 3 sagt und 2 liefert, ist ein
    kaputter Auftrag, und ein kaputter Auftrag darf nicht entstehen.

    Die Funktion wird **zweimal** gerufen, und ``code`` sagt, welcher Aufruf es ist:

    - ``400`` auf dem *Plan*, vor der ersten Objektnummer. Eine Abweichung ist hier eine
      Eingabe, die der Mensch korrigieren kann (zwei Stücke gewählt, drei verlangt) –
      und sie kostet keine Nummer.
    - ``500`` auf dem *Ergebnis*, nach dem Anlegen. Dort ist sie nur noch erreichbar,
      wenn dieser Code kaputt ist; ein Eingabefehler ist sie dann nicht mehr.
    """
    for want, got, label in counts:
        if want != got:
            raise HTTPException(
                status_code=code,
                detail=(
                    f"{label}: verlangt sind {want} Einzelinstanzen, es sind {got}. "
                    f"Die Freigabe wird abgebrochen."
                ),
            )
