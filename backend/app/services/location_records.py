"""Lagerplatz = Instanz eines ``is_location``-Artikels (F).

Ein Lagerplatz wird über **Artikel + Instanz** abgebildet (Vereinheitlichung), das
bestehende `/erp/storage-locations`-API und die `location_type='lagerplatz'`-Semantik
bleiben aber stabil: die **Instanz** ist die (scan-/bewegbare) Identität des Lagerplatzes
(``object_id``), der **Artikel** trägt die geteilten Typ-Eigenschaften – **Bezeichnung**,
**Abmessung** (``size``, «BxTxH») und **Traglast** (``max_load_kg``). Standort/Geo,
Bemerkung und die **Kapazität** («Lagermenge» = ``quantity``) leben an der Instanz. Diese
eine Stelle projiziert Instanz+Artikel auf die stabile ``StorageLocationResponse``-Form und
kapselt Anlage/Änderung/Ersetzen.
"""

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Instance
from ..models.base import utcnow
from ..schemas.storage_location import StorageLocationResponse
from .admin import get_or_create_settings, log_audit
from .objects import next_object_id
from .quantity import to_qty

LOCATION_ARTICLE_NAME = "Lagerplatz"


def _dims_to_size(w: Optional[int], d: Optional[int], h: Optional[int]) -> Optional[str]:
    parts = [str(int(x)) for x in (w, d, h) if x is not None]
    return "x".join(parts) if parts else None


def _size_to_dims(size: Optional[str]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    if not size:
        return (None, None, None)
    out: list[Optional[int]] = []
    for part in str(size).lower().replace("×", "x").split("x")[:3]:
        part = part.strip()
        try:
            out.append(int(float(part)))
        except (TypeError, ValueError):
            out.append(None)
    while len(out) < 3:
        out.append(None)
    return (out[0], out[1], out[2])


def backing_article(db: Session, inst: Instance) -> Optional[Article]:
    return db.query(Article).filter(Article.id == inst.article_id).first()


def get_instance(db: Session, object_id: int) -> Instance:
    inst = (
        db.query(Instance)
        .filter(Instance.object_id == object_id, Instance.is_location == True,
                Instance.is_active == True)
        .first()
    )
    if not inst:
        raise HTTPException(404, detail="Lagerplatz nicht gefunden")
    return inst


def to_response(db: Session, inst: Instance) -> StorageLocationResponse:
    art = backing_article(db, inst)
    w, d, h = _size_to_dims(art.size if art else None)
    replaced_by = art.replaced_by_id if art else None
    replaces = None
    if art and art.object_id:
        pred = db.query(Article.object_id).filter(Article.replaced_by_id == art.object_id).first()
        replaces = pred[0] if pred else None
    return StorageLocationResponse(
        id=inst.id,
        object_id=inst.object_id,
        status=(art.status if art else "released"),
        name=(art.name if art else LOCATION_ARTICLE_NAME),
        code=None,
        location_type=None,
        note=inst.note,
        max_load_kg=(art.max_load_kg if art else None),
        width_mm=w, depth_mm=d, height_mm=h,
        is_dry=False, is_tempered=False, is_hazmat=False, is_blocked=False,
        latitude=inst.latitude, longitude=inst.longitude,
        address_street=inst.address_street, address_zip=inst.address_zip,
        address_city=inst.address_city, address_country=inst.address_country,
        is_active=inst.is_active,
        created_at=inst.created_at, updated_at=inst.updated_at,
        replaced_by_id=replaced_by, replaces_id=replaces,
        capacity=inst.quantity,
        article_object_id=(art.object_id if art else None),
    )


def list_locations(db: Session) -> list[StorageLocationResponse]:
    rows = (
        db.query(Instance)
        .filter(Instance.is_location == True, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )
    return [to_response(db, i) for i in rows]


def create(db: Session, data, actor_id: int) -> StorageLocationResponse:
    """Neuen Lagerplatz anlegen: is_location-Artikel (Typ) + eine Instanz (Ort)."""
    company = get_or_create_settings(db)
    art = Article(
        object_id=next_object_id(db, "article"),
        status="draft", is_location=True,
        name=(getattr(data, "name", None) or LOCATION_ARTICLE_NAME),
        unit="Stk", serialization="unit",
        size=_dims_to_size(data.width_mm, data.depth_mm, data.height_mm),
        max_load_kg=data.max_load_kg,
    )
    db.add(art)
    db.flush()
    cap = to_qty(getattr(data, "capacity", None)) if getattr(data, "capacity", None) is not None else Decimal("0")
    inst = Instance(
        object_id=next_object_id(db, "instance"),
        article_id=art.id, order_id=None, is_location=True,
        kind="batch", quantity=cap,
        quality="passed", disposition="in_stock", released_at=utcnow(),
        note=data.note,
        latitude=data.latitude, longitude=data.longitude,
        address_street=data.address_street, address_zip=data.address_zip,
        address_city=data.address_city, address_country=data.address_country,
        location_type="company", location_id=company.object_id,
    )
    db.add(inst)
    db.flush()
    log_audit(db, "instances", None, "Lagerplatz angelegt", actor_id, object_id=inst.object_id)
    db.commit()
    db.refresh(inst)
    return to_response(db, inst)


# Felder, die an den **Artikel** (Typ) gehen bzw. an die **Instanz** (Ort).
_ARTICLE_FIELDS = {"name", "max_load_kg"}
_INSTANCE_FIELDS = {"note", "latitude", "longitude", "address_street", "address_zip",
                    "address_city", "address_country"}


def update(db: Session, inst: Instance, payload: dict, actor_id: int) -> StorageLocationResponse:
    art = backing_article(db, inst)
    # Abmessung (w/d/h) → Artikel.size
    if any(k in payload for k in ("width_mm", "depth_mm", "height_mm")) and art:
        w = payload.get("width_mm", None); d = payload.get("depth_mm", None); h = payload.get("height_mm", None)
        cur_w, cur_d, cur_h = _size_to_dims(art.size)
        art.size = _dims_to_size(w if "width_mm" in payload else cur_w,
                                 d if "depth_mm" in payload else cur_d,
                                 h if "height_mm" in payload else cur_h)
    if "status" in payload and art:
        art.status = payload["status"]
    if "capacity" in payload and payload["capacity"] is not None:
        inst.quantity = to_qty(payload["capacity"])
    for key, value in payload.items():
        if key in _ARTICLE_FIELDS and art:
            setattr(art, key, value)
        elif key in _INSTANCE_FIELDS:
            setattr(inst, key, value)
    log_audit(db, "instances", None, "Lagerplatz geändert", actor_id, object_id=inst.object_id)
    db.commit()
    db.refresh(inst)
    return to_response(db, inst)


def replace(db: Session, inst: Instance, actor_id: int) -> StorageLocationResponse:
    """Ersetzen: Duplikat (neuer Artikel + Instanz, Entwurf) anlegen, verknüpfen, Original
    inaktiv setzen. Liefert den **neuen** Lagerplatz."""
    old_art = backing_article(db, inst)
    new_art = Article(
        object_id=next_object_id(db, "article"),
        status="draft", is_location=True,
        name=(old_art.name if old_art else LOCATION_ARTICLE_NAME),
        unit="Stk", serialization="unit",
        size=(old_art.size if old_art else None),
        max_load_kg=(old_art.max_load_kg if old_art else None),
    )
    db.add(new_art)
    db.flush()
    company = get_or_create_settings(db)
    new_inst = Instance(
        object_id=next_object_id(db, "instance"),
        article_id=new_art.id, order_id=None, is_location=True,
        kind="batch", quantity=inst.quantity,
        quality="passed", disposition="in_stock", released_at=utcnow(),
        note=inst.note,
        latitude=inst.latitude, longitude=inst.longitude,
        address_street=inst.address_street, address_zip=inst.address_zip,
        address_city=inst.address_city, address_country=inst.address_country,
        location_type="company", location_id=company.object_id,
    )
    db.add(new_inst)
    db.flush()
    if old_art:
        old_art.replaced_by_id = new_art.object_id
        old_art.status = "inactive"
    inst.is_active = False
    log_audit(db, "instances", "replaced_by", str(new_inst.object_id), actor_id, object_id=inst.object_id)
    db.commit()
    db.refresh(new_inst)
    return to_response(db, new_inst)


def in_use(db: Session, inst: Instance) -> bool:
    """Lagern Instanzen an diesem Lagerplatz (dann nicht deaktivierbar)?"""
    return (
        db.query(Instance.id)
        .filter(Instance.is_active == True, Instance.location_type == "lagerplatz",
                Instance.location_id == inst.object_id)
        .first()
        is not None
    )
