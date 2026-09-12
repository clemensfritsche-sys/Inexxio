"""**Halter auflösen** — eine Objektnummer, ein Name, ein Typ.

Die eine Frage, die drei Stellen stellen: der **Modul-Editor** («welches Regal ist
100000456?»), der **Scanner** («gibt es diese Nummer überhaupt?») und jede Anzeige, die
einen Ort zeigt. Ein Endpunkt für alle drei – drei wären drei Antworten auf dieselbe
Frage.

Bewusst **kein** neuer Datensatztyp und keine Liste: ein Halter ist nichts Eigenes, er
ist ein Regal, eine Person oder ein Unternehmen, das gerade etwas trägt. Wer suchen will,
sucht im Feed – dort stehen sie alle.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.place import PlaceRef
from ..services import places as places_svc

router = APIRouter(prefix="/api/v1/erp/places", tags=["places"])


@router.get("", response_model=list[PlaceRef])
async def search_places(
    search: str = Query("", description="Objektnummer-Teil oder Name"),
    limit: int = Query(places_svc.SEARCH_LIMIT, ge=1, le=50),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Halter suchen** – nach Nummer oder Namen, für jede Zielort-Eingabe.

    Es ist die **Vorschlagsquelle** für das Zielfeld im Editor und für den Zielort-Scan
    zur Laufzeit. Beide fragen dieselbe Stelle: eine Liste, die etwas anbietet, das die
    Prüfung danach abweist, wäre schlimmer als keine.

    Ohne Suchbegriff kommt nichts – eine Vorschlagsliste ist eine Abkürzung beim Tippen,
    kein Katalog zum Durchblättern.
    """
    return [
        PlaceRef(object_id=s.object_id, kind=s.kind, label=s.label)
        for s in places_svc.search(db, search, limit=limit)
    ]


@router.get("/{object_id}", response_model=PlaceRef)
async def resolve_place(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Kann diese Objektnummer etwas halten? Dann: was ist sie und wie heisst sie.

    **404 heisst «kein gültiger Halter»** und ist eine Antwort, keine Panne: eine
    Artikelnummer, eine Auftragsnummer oder eine Zahl, die es nicht gibt, sind kein Ort.
    Genau daran erkennt der Scanner einen Fehlgriff, bevor er ihn quittiert.
    """
    station = places_svc.station_of(db, object_id)
    if station is None:
        raise HTTPException(
            status_code=404,
            detail=(f"{object_id} ist kein Ort. Ein Ziel ist ein Regal oder ein anderer "
                    f"Behälter (Instanz), eine Person oder ein Unternehmen."),
        )
    return PlaceRef(object_id=station.object_id, kind=station.kind, label=station.label)
