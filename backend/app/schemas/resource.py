from typing import Optional

from pydantic import BaseModel

from .article_process_step import ResourceLineView


class ResourcePlanItem(BaseModel):
    """Eine FIFO-Verbrauchsposition (Vorschau/Protokoll): Quelle + Menge + Ziel-Instanz."""

    instance_id: int
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    into_instance_id: Optional[int] = None   # in welche Produkt-Instanz verbaut
    split_from: Optional[int] = None          # Teilcharge aus dieser Instanz


class ResourceCandidate(BaseModel):
    """Wählbares Betriebsmittel (freigegebene Instanz des Werkzeug-Artikels)."""

    object_id: int
    label: str


class ResourceLineExec(ResourceLineView):
    """Ressourcen-Zeile mit Ausführungs-Infos (Verbrauch: FIFO-Plan/Verfügbarkeit;
    Betriebsmittel: wählbare Instanzen). ``mode`` (consume|tool) folgt aus dem
    Schritttyp und steuert die Anzeige im Auftrag."""

    mode: str = "consume"
    # consume (Bruchmengen möglich – kg/m²/…)
    need: Optional[float] = None
    available: Optional[float] = None
    sufficient: Optional[bool] = None
    plan: list[ResourcePlanItem] = []
    # tool
    candidates: list[ResourceCandidate] = []
    # nach Ausführung: verbrauchte bzw. genutzte Instanz-Objektnummern
    picked: list[int] = []


class ResourceComponentPick(BaseModel):
    """Welche Komponenten-Instanz (+ Menge) in eine Produkt-Instanz geht."""

    article_id: int
    article_name: Optional[str] = None
    instance_id: int
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    split_from: Optional[int] = None


class ResourceProductPlan(BaseModel):
    """Verbrauch je Produkt-Instanz: welche Komponenten konkret eingebaut werden.

    Macht den Verbrauch greifbar – «welche Instanz wird in welche Produkt-Instanz
    verbaut» statt nur einer Gesamtmenge."""

    instance_id: int            # Objektnummer der Produkt-Instanz
    kind: Optional[str] = None  # unit | batch
    quantity: float = 1         # Bruchmenge möglich (Charge à 2.5 kg)
    components: list[ResourceComponentPick] = []


class ResourceEmbed(BaseModel):
    """Eingebetteter Stand des Ressource-Schritts (im Auftrag)."""

    done: bool = False
    used_by_name: Optional[str] = None
    note: Optional[str] = None
    lines: list[ResourceLineExec] = []
    # Verbrauch je Produkt-Instanz (Vorschau bzw. Protokoll) – Kernsicht der Ausführung
    products: list[ResourceProductPlan] = []


class ResourceToolPick(BaseModel):
    """Auswahl der genutzten Betriebsmittel-Instanzen je Werkzeug-Artikel."""

    article_id: int
    instance_ids: list[int] = []


class ResourceUpdate(BaseModel):
    """Ausführung des Ressource-Schritts: Verbrauch läuft automatisch (FIFO),
    nur die Betriebsmittel werden aktiv gewählt."""

    tools: list[ResourceToolPick] = []
    note: Optional[str] = None
    step_id: Optional[int] = None   # konkrete Schritt-Definition (Mehr-Operationen-Routing)
