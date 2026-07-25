import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, Order, UserProfile
from ..schemas.instance import (
    InstanceLocation,
    InstanceOrderRef,
    InstanceResponse,
    LocationHop,
)
from ..services import location_split
from ..services.locations import location_chain, location_labels, physical_location_labels
from ..services.references import instance_orders

logger = logging.getLogger(__name__)

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


def safe_location_path(db: Session, inst: Instance) -> list[LocationHop]:
    """Standort-Kette fürs Detail – **niemals fatal**.

    Die Kette ist eine *abgeleitete Dekoration*, nicht der Datensatz: sie löst fremde
    Halter auf (Lagerplatz/Person/Unternehmen, über mehrere Stufen) und kann dabei an
    Altdaten scheitern, die die Instanz selbst gar nicht braucht. Ein Auflösungsfehler
    darf den Datensatz deshalb NIE unlesbar machen – er kostet die Kette, nicht die
    Instanz. Der echte Fehler geht mit Objektnummer ins Log, statt still zu verschwinden.
    """
    try:
        return [
            LocationHop(**hop)
            for hop in location_chain(db, inst.location_type, inst.location_id)
        ]
    except Exception:
        logger.exception(
            "Standort-Kette für Instanz %s (%s:%s) nicht auflösbar – Detail ohne Kette",
            inst.object_id, inst.location_type, inst.location_id,
        )
        return []


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
    resp = _denorm(db, [inst])[0]
    resp.location_path = safe_location_path(db, inst)
    return resp


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
