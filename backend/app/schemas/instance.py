"""Instanz und Einzelinstanz – die API-Form, **nur lesend**.

Die Menge steht überall als **Anzahl** da, nie als Dezimalzahl: eine Einzelinstanz ist
genau ein Stück, also ist die Menge einer Instanz ihre Anzahl Einzelinstanzen. Es gibt
kein Mengen-Feld, das man setzen könnte.

Es gibt auch keine **Eingabe**-Form mehr: eine Einzelinstanz entsteht mit ihrer Instanz
und die mit einem Auftrag; gelöscht wird nie. Und die Gruppe trägt **keinen Zustand** –
den haben nur ihre Stücke (Testnotizen #675/#678/#679).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstanceUnitResponse(BaseModel):
    """Eine Einzelinstanz – das Arbeitsobjekt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    suffix: int
    number: str          # <Objektnummer der Instanz>-<suffix>, die sichtbare Identität
    status: str
    #: In welchem Auftrag läuft dieses Stück gerade? ``None`` = in keinem. Das ist
    #: dieselbe Aussage wie ``status == im_prozess``, nur brauchbar: sie sagt **wo**.
    order_object_id: Optional[int] = None
    created_at: datetime


class StockState(BaseModel):
    """Ein Zustand mit seiner Menge – ein Segment der Bestandsleiste.

    Die Aufstellung ersetzt den Zustand, den eine Gruppe nicht haben kann: nicht «diese
    Instanz ist freigegeben», sondern «3 freigegeben, 1 im Prozess».
    """

    status: str
    quantity: int


class InstanceResponse(BaseModel):
    """Instanz – die Gruppe, mit ihrer Menge und ihrer Aufstellung.

    ``quantity`` ist **gezählt**, nicht gespeichert – die Instanz hat keine Mengen-Spalte.

    Einen ``status`` trägt sie nicht: eine Gruppe hat keinen Zustand, nur ihre Stücke
    haben einen (Testnotiz #675). ``states`` zählt darum auf, statt zu behaupten.

    **Die Nummern der Stücke stehen nicht drin.** Sie kommen seitenweise über
    ``GET /erp/instances/{id}/units`` – eine 5000er-Charge hier vollständig mitzuliefern
    hiesse, jedes Öffnen der Instanz so teuer zu machen wie die ganze Charge, und die
    Oberfläche müsste 5000 Zeilen auf einmal zeichnen.
    """

    id: int
    object_id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    kind: str
    label: Optional[str] = None
    quantity: int
    states: list[StockState] = []
    created_at: datetime
    updated_at: datetime
    is_active: bool


class InstanceSummary(BaseModel):
    """Feed-Zeile: ohne die Einzelinstanzen, aber mit ihrer Anzahl **und Aufstellung**.

    ``quantity`` ist die Summe über ``states`` – dieselbe Abfrage, zwei Lesarten. Die
    Zeile behauptet damit keinen Zustand (den hat eine Gruppe nicht), sondern zählt auf.
    """

    id: int
    object_id: int
    article_id: int
    article_name: Optional[str] = None
    kind: str
    label: Optional[str] = None
    quantity: int
    states: list[StockState] = []
    created_at: datetime
    updated_at: datetime
    is_active: bool


class UnitPage(BaseModel):
    """Eine Seite Einzelinstanz-Nummern – plus wie viele es insgesamt sind."""

    units: list[InstanceUnitResponse]
    total: int


class ArticleStock(BaseModel):
    """**Der Bestand eines Artikels** – die eine Antwort auf «was habe ich davon».

    Drei Ebenen in einer Antwort, und keine davon ist ein gespeichertes Feld:
    ``states``/``total`` beschreiben **alle** Stücke des Artikels (nicht nur die
    angezeigte Seite), ``instances`` ist eine Seite Instanzen mit je ihrer eigenen
    Aufstellung, und die Nummern der Stücke holt die Ebene darunter
    (``GET /erp/instances/{id}/units``) – erst auf Klick, nie auf Vorrat.
    """

    states: list[StockState]
    total: int
    instance_total: int
    instances: list[InstanceSummary]


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # instance | article | user | organization
    object_id: int
    label: str
    at: datetime
