"""Instanzen und Einzelinstanzen – **lesen**.

Die Instanz ist ein Ordner mit einer Objektnummer; gearbeitet wird an der Einzelinstanz.
Alles, was hier eine Menge nennt, hat sie gezählt – gespeichert ist sie nirgends.

**Es gibt keinen Schreib-Endpunkt mehr.** Eine Einzelinstanz entsteht ausschliesslich
mit ihrer Instanz, und die ausschliesslich mit einem Auftrag (Testnotiz #678); und
gelöscht wird sie nie – ihre Nummer ist eine Identität, keine Position (#679). Die
früheren drei Wege daneben (Instanz anlegen, Einzelinstanz nachschieben, Einzelinstanz
deaktivieren) waren Türen, durch die Material ohne Auftrag, ohne Prozess und ohne
Ereignis in die Welt kam und wieder verschwand.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..domain import statuses as st
from ..models import Article, Instance, InstanceUnit, UserProfile
from ..schemas.instance import (
    Genealogy, GenealogyHost, GenealogyPart, InstanceResponse, InstanceSummary,
    InstanceUnitResponse, UnitPage, stock_states,
)
from ..schemas.place import PlaceRef, UnitPlace
from ..services import genealogy, instances as inst_svc, places as places_svc, process

router = APIRouter(prefix="/api/v1/erp/instances", tags=["instances"])


def _article(db: Session, instance: Instance) -> Article | None:
    return db.query(Article).filter(Article.id == instance.article_id).first()


def _place_out(chain: list) -> UnitPlace | None:
    """Eine aufgelöste Kette → die Antwortform. Leer heisst **standortlos**."""
    if not chain:
        return None
    refs = [PlaceRef(object_id=s.object_id, kind=s.kind, label=s.label) for s in chain]
    return UnitPlace(holder=refs[0], chain=refs)


def _unit_out(instance: Instance, unit: InstanceUnit,
              holders: dict[int, int], parts: dict[int, int],
              places: dict[int, list]) -> InstanceUnitResponse:
    return InstanceUnitResponse(
        id=unit.id,
        suffix=unit.suffix,
        number=inst_svc.unit_number(instance, unit),
        status=unit.status,
        order_object_id=holders.get(unit.id),
        parts_count=parts.get(unit.id, 0),
        place=_place_out(places.get(unit.id, [])),
        created_at=unit.created_at,
    )


def _detail(db: Session, instance: Instance) -> InstanceResponse:
    article = _article(db, instance)
    by_status = inst_svc.states(db, [instance.id]).get(instance.id, {})
    return InstanceResponse(
        id=instance.id,
        object_id=instance.object_id,
        article_id=instance.article_id,
        article_object_id=article.object_id if article else None,
        article_name=article.name if article else None,
        kind=instance.kind,
        label=instance.label,
        quantity=sum(by_status.values()),
        states=stock_states(by_status),
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        is_active=instance.is_active,
    )


def _get(db: Session, object_id: int) -> Instance:
    instance = db.query(Instance).filter(Instance.object_id == object_id).first()
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Instanz {object_id} nicht gefunden.")
    return instance


@router.get("", response_model=list[InstanceSummary])
def list_instances(
    search: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Der Instanz-Feed – **alle** Instanzen, neueste Objektnummer zuerst.

    Der frühere Filter ``article_object_id`` ist entfallen: «was habe ich von diesem
    Artikel» beantwortet ``GET /erp/articles/{id}/stock``, samt Aufstellung. Zwei Wege
    zu derselben Frage sind auch dann einer zu viel, wenn der zweite niemanden hat –
    dieser hatte keinen einzigen Aufrufer.
    """
    q = db.query(Instance).filter(Instance.is_active.is_(True))
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.join(Article, Article.id == Instance.article_id, isouter=True).filter(
            or_(cast(Instance.object_id, String).ilike(like), Article.name.ilike(like))
        )
    rows = q.order_by(Instance.object_id.desc()).limit(limit).offset(offset).all()

    by_instance = inst_svc.states(db, [i.id for i in rows])
    names = {
        a.id: a.name
        for a in db.query(Article).filter(Article.id.in_([i.article_id for i in rows])).all()
    } if rows else {}
    return [
        InstanceSummary(
            id=i.id, object_id=i.object_id, article_id=i.article_id,
            article_name=names.get(i.article_id), kind=i.kind,
            label=i.label,
            quantity=sum(by_instance.get(i.id, {}).values()),
            states=stock_states(by_instance.get(i.id, {})),
            created_at=i.created_at, updated_at=i.updated_at, is_active=i.is_active,
        )
        for i in rows
    ]


@router.get("/{object_id}", response_model=InstanceResponse)
def get_instance(
    object_id: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return _detail(db, _get(db, object_id))


@router.get("/{object_id}/units", response_model=UnitPage)
def instance_units(
    object_id: int,
    status: list[str] | None = Query(None, description="Nur Stücke in diesen Zuständen"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """Die **Nummern** der Einzelinstanzen – seitenweise, auf Nachfrage.

    Die unterste Ebene der Bestandsansicht. Sie wird erst geholt, wenn jemand sie
    aufklappt: eine 5000er-Charge trägt 5000 Nummern, und die auf Vorrat mitzuliefern
    macht jede Instanz-Zeile so teuer wie die ganze Charge.
    """
    for value in status or []:
        st.assert_known(value, field="status")
    instance = _get(db, object_id)
    rows, total = inst_svc.units_page(
        db, instance, statuses=status, limit=limit, offset=offset)
    holders = process.holders(db, [u.id for u in rows])
    # Nur die **Zahl** – zwei Abfragen für die ganze Seite. Die Stückliste selbst kommt
    # auf Klick; sie ist je Stück eine eigene Geschichte und gehört in keine Liste.
    parts = genealogy.parts_counts(db, [u.id for u in rows])
    # **Wo sie liegen** – aufgelöst je Halter, nicht je Stück (``places.for_units``).
    # 60 Schrauben in einem Regal sind eine Kette; je Zeile aufzulösen wäre die
    # N+1-Falle, an der die Ortsanzeige des Vorgängers hing.
    places = places_svc.for_units(db, rows)
    return UnitPage(
        units=[_unit_out(instance, u, holders, parts, places) for u in rows],
        total=total)


@router.get("/{object_id}/units/{suffix}/genealogy", response_model=Genealogy)
def unit_genealogy(
    object_id: int,
    suffix: int,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    """**Woraus besteht dieses Stück – und worin steckt es?**

    Beides ist eine Ableitung über den Ereignis-Log (``services/genealogy``), kein
    gespeichertes Feld: die Stückliste sind die Stücke, die einen gemeinsamen Auftrag als
    ``Verbaut`` verlassen haben.

    **Erst auf Klick**, wie die Nummern selbst: eine Baugruppe kann hunderte Teile haben,
    und sie in jede Zeile der Stückliste mitzuliefern hiesse, die Genealogie bei jedem
    Öffnen einer Charge vollständig aufzulösen.
    """
    instance = _get(db, object_id)
    unit = (
        db.query(InstanceUnit)
        .filter(InstanceUnit.instance_id == instance.id, InstanceUnit.suffix == suffix)
        .first()
    )
    if unit is None:
        raise HTTPException(
            status_code=404,
            detail=f"Einzelinstanz {object_id}-{suffix} gibt es nicht.",
        )
    return Genealogy(
        parts=[GenealogyPart(**p) for p in genealogy.parts_of(db, unit)],
        built_into=[
            GenealogyHost(
                order_object_id=h["order_object_id"],
                products=[GenealogyPart(**p) for p in h["products"]],
            )
            for h in genealogy.built_into(db, unit)
        ],
    )
