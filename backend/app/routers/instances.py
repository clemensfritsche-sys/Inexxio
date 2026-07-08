from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, UserProfile
from ..schemas.instance import InstanceLocation, InstanceMoveInput, InstanceOrderRef, InstanceResponse
from ..services import location_split
from ..services.admin import log_audit
from ..services.events import emit
from ..services.locations import location_labels, physical_location_labels, validate_location
from ..services.references import instance_orders

router = APIRouter(prefix="/api/v1/erp/instances", tags=["instances"])


class CountResponse(BaseModel):
    count: int


def _apply_search(q, search: str):
    """Server-seitige Suche: Instanz-Objektnummer, Artikelname oder Artikel-Nummer."""
    s = search.strip()
    if not s:
        return q
    like = f"%{s}%"
    return q.join(Article, Article.id == Instance.article_id, isouter=True).filter(
        or_(
            cast(Instance.object_id, String).ilike(like),
            Article.name.ilike(like),
            cast(Article.object_id, String).ilike(like),
        )
    )


def _denorm(db: Session, rows: list[Instance]) -> list[InstanceResponse]:
    art_ids = {r.article_id for r in rows}
    ord_ids = {r.order_id for r in rows}
    art_rows = db.query(Article).filter(Article.id.in_(art_ids)).all() if art_ids else []
    arts_name = {a.id: a.name for a in art_rows}
    arts_oid = {a.id: a.object_id for a in art_rows}
    resv_ids = {r.reserved_for_order_id for r in rows if r.reserved_for_order_id}
    all_ord_ids = ord_ids | resv_ids
    ords = {o.id: o.object_id for o in db.query(Order).filter(Order.id.in_(all_ord_ids)).all()} if all_ord_ids else {}
    # Standort-Verteilung je Instanz (Charge kann auf mehrere Orte verteilt sein) +
    # ALLE Standort-Labels **batch** auflösen (scalar + jede Teilmenge), damit weder der
    # Feed noch das Detail N+1-Queries auslöst.
    dist_by_inst = {r.id: location_split.distribution(r) for r in rows}
    loc_keys = {(r.location_type, r.location_id) for r in rows}
    for dist in dist_by_inst.values():
        loc_keys.update((d["location_type"], d["location_id"]) for d in dist)
    loc_keys = list(loc_keys)
    loc_labels = location_labels(db, loc_keys)
    phys_labels = physical_location_labels(
        db, [k for k in loc_keys if k[0] == "instance"])
    out: list[InstanceResponse] = []
    for r in rows:
        resp = InstanceResponse.model_validate(r)
        resp.article_name = arts_name.get(r.article_id)
        resp.article_object_id = arts_oid.get(r.article_id)
        resp.order_object_id = ords.get(r.order_id)
        resp.reserved_for_order_object_id = ords.get(r.reserved_for_order_id) if r.reserved_for_order_id else None
        resp.location_label = loc_labels.get((r.location_type, r.location_id))
        if r.location_type == "instance":
            resp.physical_location_label = phys_labels.get((r.location_type, r.location_id))
        resp.locations = [
            InstanceLocation(
                location_type=d["location_type"], location_id=d["location_id"],
                quantity=d["quantity"],
                location_label=loc_labels.get((d["location_type"], d["location_id"])),
            )
            for d in dist_by_inst.get(r.id, [])
        ]
        out.append(resp)
    return out


@router.get("", response_model=list[InstanceResponse])
async def list_instances(
    limit: int = Query(0, ge=0, le=1000, description="0 = keine Begrenzung; sonst Seitengröße"),
    offset: int = Query(0, ge=0),
    search: str = Query("", description="Suche: Objektnummer, Artikelname oder Artikel-Nummer"),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Instanz-Feed (höchste Kardinalität) – server-seitig paginierbar
    (``limit``/``offset``, neueste zuerst) und durchsuchbar (``search``)."""
    q = _apply_search(
        db.query(Instance).filter(Instance.is_active == True), search
    ).order_by(Instance.object_id.desc())
    if limit:
        q = q.offset(offset).limit(limit)
    rows = q.all()
    return _denorm(db, rows)


@router.get("/count", response_model=CountResponse)
async def count_instances(
    search: str = Query(""),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Gesamtzahl (matchender) Instanzen – für die Feed-Zähler/Pagination."""
    q = _apply_search(db.query(Instance.id).filter(Instance.is_active == True), search)
    return CountResponse(count=int(q.count()))


@router.get("/{object_id}", response_model=InstanceResponse)
async def get_instance(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    return _denorm(db, [inst])[0]


# Kein eigener Dokumente-Endpunkt je Instanz mehr: der Reiter «Dokumente» läuft für
# ALLE Objekte über den generischen ``GET /erp/objects/{id}/documents`` (document_files.py).

@router.get("/{object_id}/orders", response_model=list[InstanceOrderRef])
async def list_instance_orders(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Alle Aufträge, die diese Instanz angefasst haben (Herkunft zuerst) – die
    Instanz ist die Summe aller Prozesse, die ein Auftrag an ihr ausgelöst hat."""
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    return [InstanceOrderRef(**r) for r in instance_orders(db, inst)]


# Standort-Verbleibe, die eine Instanz endgültig aus dem Bestand nehmen – nicht mehr bewegbar.
_TERMINAL_DISPOSITIONS = ("consumed", "sold", "scrapped")


@router.post("/{object_id}/move", response_model=InstanceResponse)
async def move_instance_part(
    object_id: int,
    data: InstanceMoveInput,
    db: Session = Depends(get_db),
    actor: UserProfile = Depends(require_employee),
):
    """Eine **Teilmenge** einer Charge an einen anderen Standort verlagern («ein Bewegen =
    ein Task»): die Objektnummer bleibt, es entsteht KEINE neue Instanz. Für Einzelteile
    (Menge 1) nur als Ganzes. Der Rest der Charge bleibt, wo er war."""
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Instanz nicht gefunden")
    if (inst.disposition or "") in _TERMINAL_DISPOSITIONS:
        raise HTTPException(409, detail="Diese Instanz ist nicht mehr im Bestand und kann nicht bewegt werden.")

    validate_location(db, data.location_type, data.location_id)
    if data.location_type == "instance" and data.location_id == inst.object_id:
        raise HTTPException(400, detail="Eine Instanz kann nicht in sich selbst liegen.")

    from ..services.quantity import to_qty
    qty = to_qty(data.quantity)
    whole = qty >= to_qty(inst.quantity)
    if inst.kind == "unit" and not whole:
        raise HTTPException(400, detail="Ein Einzelteil kann nur als Ganzes bewegt werden.")

    if whole and not inst.locations:
        # Ganze (nicht verteilte) Instanz → einfacher Standortwechsel.
        location_split.set_single(inst, data.location_type, data.location_id)
    else:
        location_split.move(inst, data.location_type, data.location_id, qty, data.from_location_id)

    log_audit(db, "instances", "location", f"{data.location_type}:{data.location_id}",
              actor.id, object_id=inst.object_id)
    emit(db, "instance.moved", object_type="instance", object_id=inst.object_id, actor_id=actor.id)
    db.commit()
    db.refresh(inst)
    return _denorm(db, [inst])[0]
