from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.objects import ObjectType, UniversalObject
from ..models.prozess_schritte import ProzessSchritt
from ..schemas.uni_objekte import (
    AusfuehrenRequest,
    SchrittCreate,
    SchrittErledigenRequest,
    SchrittResponse,
    SchrittUpdate,
    UniObjektCreate,
    UniObjektDetail,
    UniObjektSummary,
    UniObjektUpdate,
)

router = APIRouter(prefix="/api/v1/uni-objekte", tags=["uni-objekte"])

_TERMINAL_STATUSES = {"VERBAUT", "GESPERRT", "VERSCHROTTET"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _instanzen_count(db: Session, objekt_id: int) -> int:
    return (
        db.query(UniversalObject)
        .filter(UniversalObject.stamm_id == objekt_id, UniversalObject.is_active == True)
        .count()
    )


def _get_schritte(db: Session, objekt_id: int) -> list[ProzessSchritt]:
    return (
        db.query(ProzessSchritt)
        .filter(ProzessSchritt.objekt_id == objekt_id, ProzessSchritt.is_active == True)
        .order_by(ProzessSchritt.position)
        .all()
    )


def _build_summary(db: Session, obj: UniversalObject) -> UniObjektSummary:
    count = _instanzen_count(db, obj.id) if obj.stamm_id is None else 0
    data = UniObjektSummary.model_validate(obj)
    return data.model_copy(update={"instanzen_count": count})


def _build_detail(db: Session, obj: UniversalObject) -> UniObjektDetail:
    schritte = _get_schritte(db, obj.id)
    count = _instanzen_count(db, obj.id) if obj.stamm_id is None else 0
    data = UniObjektDetail(
        id=obj.id,
        stamm_id=obj.stamm_id,
        name=obj.name,
        obj_status=obj.obj_status,
        menge=obj.menge,
        einheit=obj.einheit,
        lagerort=obj.lagerort,
        notiz=obj.notiz,
        schritt_protokoll=obj.schritt_protokoll,
        schritte=[SchrittResponse.model_validate(s) for s in schritte],
        instanzen_count=count,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
    return data


def _build_protokoll(schritte: list[ProzessSchritt]) -> list[dict]:
    result = []
    for i, s in enumerate(schritte):
        result.append({
            "position": s.position,
            "beschreibung": s.beschreibung,
            "status": "aktiv" if i == 0 else "ausstehend",
            "ressourcen": s.ressourcen,
            "daten_felder": s.daten_felder,
            "ergebnis_optionen": s.ergebnis_optionen,
            "referenz_objekt_id": s.referenz_objekt_id,
            "referenz_menge": s.referenz_menge or 1,
            "ausgefuehrt_von": None,
            "ausgefuehrt_am": None,
            "ergebnis": None,
            "erfasste_daten": None,
        })
    return result


def _create_referenz_instanzen(
    db: Session, referenz_objekt_id: int, menge: int, created_by: int
) -> None:
    stamm = db.query(UniversalObject).filter(
        UniversalObject.id == referenz_objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.obj_status == "FREIGEGEBEN",
        UniversalObject.stamm_id == None,  # noqa: E711
        UniversalObject.is_active == True,
    ).first()
    if not stamm:
        return
    ref_schritte = _get_schritte(db, stamm.id)
    ref_protokoll = _build_protokoll(ref_schritte)
    for _ in range(menge):
        inst = UniversalObject(
            object_type=ObjectType.OBJEKT,
            created_by=created_by,
            updated_by=created_by,
            stamm_id=stamm.id,
            name=stamm.name,
            obj_status="IN_PRODUKTION",
            einheit=stamm.einheit,
            schritt_protokoll=list(ref_protokoll),
        )
        db.add(inst)


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_uni_objekte(
    stamm: Optional[bool] = Query(None, description="True=templates, False=instances, None=all"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    query = db.query(UniversalObject).filter(
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    )
    if stamm is True:
        query = query.filter(UniversalObject.stamm_id == None)  # noqa: E711
    elif stamm is False:
        query = query.filter(UniversalObject.stamm_id != None)  # noqa: E711
    if q:
        query = query.filter(UniversalObject.name.ilike(f"%{q}%"))

    total = query.count()
    objs = (
        query.order_by(UniversalObject.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_build_summary(db, o) for o in objs]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ─── Create template ──────────────────────────────────────────────────────────

@router.post("", response_model=UniObjektDetail, status_code=status.HTTP_201_CREATED)
async def create_uni_objekt(
    data: UniObjektCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = UniversalObject(
        object_type=ObjectType.OBJEKT,
        created_by=current_user.id,
        updated_by=current_user.id,
        name=data.name,
        obj_status="ENTWURF",
        einheit=data.einheit or "Stk",
        notiz=data.notiz,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _build_detail(db, obj)


# ─── Lookup FREIGEGEBEN template by number ───────────────────────────────────

@router.get("/lookup/{objekt_nr}", response_model=UniObjektDetail)
async def lookup_by_nummer(
    objekt_nr: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_nr,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.obj_status == "FREIGEGEBEN",
        UniversalObject.stamm_id == None,  # noqa: E711
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Kein freigegebenes Objekt mit dieser Nummer gefunden")
    return _build_detail(db, obj)


# ─── Get ──────────────────────────────────────────────────────────────────────

@router.get("/{objekt_id}", response_model=UniObjektDetail)
async def get_uni_objekt(
    objekt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    return _build_detail(db, obj)


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{objekt_id}", response_model=UniObjektDetail)
async def update_uni_objekt(
    objekt_id: int,
    data: UniObjektUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    if obj.obj_status not in ("ENTWURF", None) and obj.stamm_id is None:
        raise HTTPException(status_code=400, detail="Nur ENTWURF-Vorlagen können bearbeitet werden")
    if obj.stamm_id is not None and obj.obj_status in _TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Abgeschlossene Instanzen können nicht geändert werden")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_at = _now()
    obj.updated_by = current_user.id
    db.commit()
    db.refresh(obj)
    return _build_detail(db, obj)


# ─── Soft-delete ──────────────────────────────────────────────────────────────

@router.delete("/{objekt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_uni_objekt(
    objekt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    if obj.obj_status != "ENTWURF":
        raise HTTPException(status_code=400, detail="Nur ENTWURF-Vorlagen können gelöscht werden")
    obj.is_active = False
    obj.updated_at = _now()
    obj.updated_by = current_user.id
    db.commit()


# ─── Freigeben (ENTWURF → FREIGEGEBEN) ───────────────────────────────────────

@router.post("/{objekt_id}/freigeben", response_model=UniObjektDetail)
async def freigeben(
    objekt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
        UniversalObject.stamm_id == None,  # noqa: E711
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if obj.obj_status != "ENTWURF":
        raise HTTPException(status_code=400, detail="Nur ENTWURF-Vorlagen können freigegeben werden")

    schritte = _get_schritte(db, obj.id)
    if not schritte:
        raise HTTPException(status_code=400, detail="Vorlage braucht mindestens einen Prozessschritt")

    obj.obj_status = "FREIGEGEBEN"
    obj.updated_at = _now()
    obj.updated_by = current_user.id
    db.commit()
    db.refresh(obj)
    return _build_detail(db, obj)


# ─── Steps: add ───────────────────────────────────────────────────────────────

@router.post("/{objekt_id}/schritte", response_model=SchrittResponse, status_code=status.HTTP_201_CREATED)
async def add_schritt(
    objekt_id: int,
    data: SchrittCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
        UniversalObject.stamm_id == None,  # noqa: E711
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if obj.obj_status != "ENTWURF":
        raise HTTPException(status_code=400, detail="Schritte können nur in ENTWURF-Vorlagen hinzugefügt werden")

    schritt = ProzessSchritt(
        objekt_id=objekt_id,
        **data.model_dump(),
    )
    db.add(schritt)
    obj.updated_at = _now()
    db.commit()
    db.refresh(schritt)
    return SchrittResponse.model_validate(schritt)


# ─── Steps: update ────────────────────────────────────────────────────────────

@router.patch("/{objekt_id}/schritte/{schritt_id}", response_model=SchrittResponse)
async def update_schritt(
    objekt_id: int,
    schritt_id: int,
    data: SchrittUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if obj.obj_status != "ENTWURF":
        raise HTTPException(status_code=400, detail="Schritte können nur in ENTWURF-Vorlagen bearbeitet werden")

    schritt = db.query(ProzessSchritt).filter(
        ProzessSchritt.id == schritt_id,
        ProzessSchritt.objekt_id == objekt_id,
        ProzessSchritt.is_active == True,
    ).first()
    if not schritt:
        raise HTTPException(status_code=404, detail="Schritt nicht gefunden")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(schritt, key, value)
    obj.updated_at = _now()
    db.commit()
    db.refresh(schritt)
    return SchrittResponse.model_validate(schritt)


# ─── Steps: delete ────────────────────────────────────────────────────────────

@router.delete("/{objekt_id}/schritte/{schritt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schritt(
    objekt_id: int,
    schritt_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if obj.obj_status != "ENTWURF":
        raise HTTPException(status_code=400, detail="Schritte können nur in ENTWURF-Vorlagen gelöscht werden")

    schritt = db.query(ProzessSchritt).filter(
        ProzessSchritt.id == schritt_id,
        ProzessSchritt.objekt_id == objekt_id,
        ProzessSchritt.is_active == True,
    ).first()
    if not schritt:
        raise HTTPException(status_code=404, detail="Schritt nicht gefunden")

    schritt.is_active = False
    obj.updated_at = _now()
    db.commit()


# ─── Ausfuehren: create N instances ──────────────────────────────────────────

@router.post("/{objekt_id}/ausfuehren", response_model=list[UniObjektSummary])
async def ausfuehren(
    objekt_id: int,
    data: AusfuehrenRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    stamm = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
        UniversalObject.stamm_id == None,  # noqa: E711
    ).first()
    if not stamm:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if stamm.obj_status != "FREIGEGEBEN":
        raise HTTPException(status_code=400, detail="Nur FREIGEGEBEN-Vorlagen können ausgeführt werden")

    schritte = _get_schritte(db, stamm.id)
    if not schritte:
        raise HTTPException(status_code=400, detail="Vorlage hat keine Prozessschritte")

    protokoll_template = _build_protokoll(schritte)
    created = []

    for _ in range(data.menge):
        instanz = UniversalObject(
            object_type=ObjectType.OBJEKT,
            created_by=current_user.id,
            updated_by=current_user.id,
            stamm_id=stamm.id,
            name=stamm.name,
            obj_status="IN_PRODUKTION",
            einheit=stamm.einheit,
            lagerort=data.lagerort,
            schritt_protokoll=list(protokoll_template),
        )
        db.add(instanz)
        created.append(instanz)

    db.commit()
    for inst in created:
        db.refresh(inst)

    return [_build_summary(db, inst) for inst in created]


# ─── List instances of a template ─────────────────────────────────────────────

@router.get("/{objekt_id}/instanzen", response_model=dict)
async def list_instanzen(
    objekt_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    stamm = db.query(UniversalObject).filter(
        UniversalObject.id == objekt_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
    ).first()
    if not stamm:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")

    query = db.query(UniversalObject).filter(
        UniversalObject.stamm_id == objekt_id,
        UniversalObject.is_active == True,
    )
    total = query.count()
    instanzen = (
        query.order_by(UniversalObject.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_build_summary(db, i) for i in instanzen],
    }


# ─── Protokoll: execute step ──────────────────────────────────────────────────

@router.post("/{instanz_id}/protokoll/{position}/erledigen", response_model=UniObjektDetail)
async def schritt_erledigen(
    instanz_id: int,
    position: int,
    data: SchrittErledigenRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    instanz = db.query(UniversalObject).filter(
        UniversalObject.id == instanz_id,
        UniversalObject.object_type == ObjectType.OBJEKT,
        UniversalObject.is_active == True,
        UniversalObject.stamm_id != None,  # noqa: E711
    ).first()
    if not instanz:
        raise HTTPException(status_code=404, detail="Instanz nicht gefunden")
    if instanz.obj_status in _TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Abgeschlossene Instanzen können nicht geändert werden")

    protokoll: list[dict] = list(instanz.schritt_protokoll or [])
    step = next((s for s in protokoll if s["position"] == position), None)
    if not step:
        raise HTTPException(status_code=404, detail="Schritt nicht gefunden")
    if step["status"] != "aktiv":
        raise HTTPException(status_code=400, detail="Dieser Schritt ist nicht aktiv")

    step["status"] = "erledigt"
    step["ergebnis"] = data.ergebnis
    step["erfasste_daten"] = data.erfasste_daten
    step["ausgefuehrt_von"] = data.ausgefuehrt_von or current_user.email
    step["ausgefuehrt_am"] = _now().isoformat()

    # Trigger referenced object instances if configured
    ref_id = step.get("referenz_objekt_id")
    ref_menge = step.get("referenz_menge") or 1
    if ref_id:
        _create_referenz_instanzen(db, ref_id, ref_menge, current_user.id)

    # Activate next step or mark complete
    positions = sorted(s["position"] for s in protokoll if s["status"] != "erledigt")
    if positions:
        next_step = next((s for s in protokoll if s["position"] == positions[0]), None)
        if next_step:
            next_step["status"] = "aktiv"
    else:
        instanz.obj_status = "VERFUEGBAR"

    instanz.schritt_protokoll = protokoll
    instanz.updated_at = _now()
    instanz.updated_by = current_user.id
    db.commit()
    db.refresh(instanz)
    return _build_detail(db, instanz)
