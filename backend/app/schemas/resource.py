from typing import Optional

from pydantic import BaseModel

from .article_process_step import ResourceLineView


class ResourcePlanItem(BaseModel):
    """Eine FIFO-Verbrauchsposition (Vorschau): Quelle + Menge."""

    instance_id: int
    quantity: int


class ResourceCandidate(BaseModel):
    """Wählbares Betriebsmittel (freigegebene Instanz des Werkzeug-Artikels)."""

    object_id: int
    label: str


class ResourceLineExec(ResourceLineView):
    """Ressourcen-Zeile mit Ausführungs-Infos (Verbrauch: FIFO-Plan/Verfügbarkeit;
    Betriebsmittel: wählbare Instanzen)."""

    # consume
    need: Optional[int] = None
    available: Optional[int] = None
    sufficient: Optional[bool] = None
    plan: list[ResourcePlanItem] = []
    # tool
    candidates: list[ResourceCandidate] = []
    # nach Ausführung: verbrauchte bzw. genutzte Instanz-Objektnummern
    picked: list[int] = []


class ResourceEmbed(BaseModel):
    """Eingebetteter Stand des Ressource-Schritts (im Auftrag)."""

    done: bool = False
    used_by_name: Optional[str] = None
    note: Optional[str] = None
    lines: list[ResourceLineExec] = []


class ResourceToolPick(BaseModel):
    """Auswahl der genutzten Betriebsmittel-Instanzen je Werkzeug-Artikel."""

    article_id: int
    instance_ids: list[int] = []


class ResourceUpdate(BaseModel):
    """Ausführung des Ressource-Schritts: Verbrauch läuft automatisch (FIFO),
    nur die Betriebsmittel werden aktiv gewählt."""

    tools: list[ResourceToolPick] = []
    note: Optional[str] = None
