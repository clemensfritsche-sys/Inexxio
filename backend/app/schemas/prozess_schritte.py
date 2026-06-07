from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProzessSchrittCreate(BaseModel):
    position: int
    beschreibung: str
    ressourcen: Optional[list[dict[str, Any]]] = None
    daten_felder: Optional[list[dict[str, Any]]] = None
    ergebnis_optionen: Optional[list[dict[str, Any]]] = None
    aktion: Optional[dict[str, Any]] = None
    onshape_link: Optional[str] = None
    dokument_link: Optional[str] = None


class ProzessSchrittUpdate(BaseModel):
    position: Optional[int] = None
    beschreibung: Optional[str] = None
    ressourcen: Optional[list[dict[str, Any]]] = None
    daten_felder: Optional[list[dict[str, Any]]] = None
    ergebnis_optionen: Optional[list[dict[str, Any]]] = None
    aktion: Optional[dict[str, Any]] = None
    onshape_link: Optional[str] = None
    dokument_link: Optional[str] = None


class ProzessSchrittResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    position: int
    beschreibung: str
    ressourcen: Optional[list[dict[str, Any]]] = None
    daten_felder: Optional[list[dict[str, Any]]] = None
    ergebnis_optionen: Optional[list[dict[str, Any]]] = None
    aktion: Optional[dict[str, Any]] = None
    onshape_link: Optional[str] = None
    dokument_link: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
