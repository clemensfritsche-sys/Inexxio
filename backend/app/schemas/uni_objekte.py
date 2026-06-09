from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class SchrittCreate(BaseModel):
    position: int
    beschreibung: str
    schritt_typ: str = "ressource"
    ressourcen: Optional[list[dict]] = None
    daten_felder: Optional[list[dict]] = None
    ergebnis_optionen: Optional[list[dict]] = None
    referenz_objekt_id: Optional[int] = None
    referenz_menge: int = 1
    onshape_link: Optional[str] = None
    dokument_link: Optional[str] = None


class SchrittUpdate(BaseModel):
    position: Optional[int] = None
    beschreibung: Optional[str] = None
    schritt_typ: Optional[str] = None
    ressourcen: Optional[list[dict]] = None
    daten_felder: Optional[list[dict]] = None
    ergebnis_optionen: Optional[list[dict]] = None
    referenz_objekt_id: Optional[int] = None
    referenz_menge: Optional[int] = None
    onshape_link: Optional[str] = None
    dokument_link: Optional[str] = None


class SchrittResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    objekt_id: Optional[int]
    position: int
    beschreibung: str
    schritt_typ: str
    ressourcen: Optional[list[dict]]
    daten_felder: Optional[list[dict]]
    ergebnis_optionen: Optional[list[dict]]
    referenz_objekt_id: Optional[int]
    referenz_menge: int
    onshape_link: Optional[str]
    dokument_link: Optional[str]


class UniObjektCreate(BaseModel):
    name: str
    notiz: Optional[str] = None
    einheit: Optional[str] = "Stk"


class UniObjektUpdate(BaseModel):
    name: Optional[str] = None
    notiz: Optional[str] = None
    einheit: Optional[str] = None
    lagerort: Optional[str] = None


class UniObjektSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stamm_id: Optional[int]
    name: Optional[str]
    obj_status: Optional[str]
    menge: Optional[Decimal]
    einheit: Optional[str]
    lagerort: Optional[str]
    parent_instanz_id: Optional[int] = None
    instanzen_count: int = 0
    created_at: datetime
    updated_at: datetime


class UniObjektDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stamm_id: Optional[int]
    name: Optional[str]
    obj_status: Optional[str]
    menge: Optional[Decimal]
    einheit: Optional[str]
    lagerort: Optional[str]
    notiz: Optional[str]
    schritt_protokoll: Optional[list[dict]]
    parent_instanz_id: Optional[int] = None
    parent_schritt_position: Optional[int] = None
    schritte: list[SchrittResponse]
    instanzen_count: int
    created_at: datetime
    updated_at: datetime


class AusfuehrenRequest(BaseModel):
    menge: int
    lagerort: Optional[str] = None

    @field_validator("menge")
    @classmethod
    def menge_range(cls, v: int) -> int:
        if not (1 <= v <= 1000):
            raise ValueError("menge must be between 1 and 1000")
        return v


class SchrittErledigenRequest(BaseModel):
    ergebnis: str
    erfasste_daten: Optional[dict[str, str]] = None
    ausgefuehrt_von: Optional[str] = None
