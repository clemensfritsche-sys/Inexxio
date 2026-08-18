"""Der Ort – ablegen, «wo ist X?», «was liegt hier?» (PROCESS_CORE §15).

Drei Endpunkte, ein Begriff. Alle drei lesen bzw. schreiben **dieselbe** Tabelle; die
beiden Fragen sind zwei Leserichtungen davon, keine zwei Wahrheiten (§15.9).

**Die Ablage verlangt keinen Auftrag.** Das ist der Kern: freier Bestand ist der
Normalzustand eines Lagers, und genau dort war «wo ist es» bisher unbeantwortbar. Ein
Endpunkt, der einen Auftrag verlangte, hätte die Lücke nicht geschlossen, sondern
verschoben.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import Article, Instance, InstanceUnit, UserProfile
from ..schemas.place import (
    HeldUnit, HolderContents, HolderRef, PlaceCreate, PlaceHop, PlaceObservation,
    PlaceResult, UnitPlaceResponse,
)
from ..services import instances as inst_svc, people, places

router = APIRouter(prefix="/api/v1/erp/places", tags=["places"])

#: Wie viele Beobachtungen die Historie höchstens zeigt. Gekappt **und ausgewiesen**
#: (``history_truncated``) – ein stiller Deckel läse sich wie Vollständigkeit.
HISTORY_LIMIT = 200


def _ref(h: places.Holder) -> HolderRef:
    return HolderRef(object_id=h.object_id, type=h.type, name=h.name)


def _unit_or_404(db: Session, unit_id: int) -> tuple[InstanceUnit, Instance]:
    unit = db.query(InstanceUnit).filter(InstanceUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(404, f"Einzelinstanz {unit_id} gibt es nicht.")
    instance = db.query(Instance).filter(Instance.id == unit.instance_id).first()
    if not instance:
        # Kann es nicht geben – und wenn doch, ist es ein Befund, keine leere Antwort.
        raise HTTPException(500, f"Einzelinstanz {unit_id} hat keine Instanz.")
    return unit, instance


@router.post("", response_model=PlaceResult, status_code=201)
def place_units(data: PlaceCreate, db: Session = Depends(get_db),
                user: UserProfile = Depends(require_employee)):
    """**Ablegen.** Je Stück eine neue Beobachtung – append-only, kein Update-Pfad.

    Ändert **nichts** ausser dem Ort: kein Status, keine Zugehörigkeit, kein Eintrag im
    Ereignis-Log (SYSTEM_LOGIC O3). Genau deshalb darf jedes Stück abgelegt werden,
    gleich in welchem Zustand es ist.
    """
    rows = places.record(db, data.instance_unit_ids, data.holder_object_id,
                         actor_id=user.id, source=data.source)
    db.commit()
    return PlaceResult(placed=len(rows),
                       holder=_ref(places.resolve_holder(db, data.holder_object_id)))


@router.get("/unit/{unit_id}", response_model=UnitPlaceResponse)
def where_is(unit_id: int, db: Session = Depends(get_db),
             _: UserProfile = Depends(require_employee)):
    """**Wo ist X?** Der aktuelle Ort, die Kette nach aussen und die Historie.

    Ohne Beobachtung ist ``holder`` leer – «nicht bekannt» ist die ehrliche Antwort,
    ein geratener Ort wäre die Alternative.
    """
    return _where(db, unit_id)


def _where(db: Session, unit_id: int) -> UnitPlaceResponse:
    unit, instance = _unit_or_404(db, unit_id)
    number = inst_svc.unit_number(instance, unit)

    holder_id = places.current_of(db, unit.id)
    if holder_id is None:
        return UnitPlaceResponse(instance_unit_id=unit.id, number=number)

    ch = places.chain(db, holder_id)
    rows = places.history(db, unit.id, limit=HISTORY_LIMIT + 1)
    shown = rows[:HISTORY_LIMIT]

    holders = places.resolve_holders(db, [r.holder_object_id for r in shown] + [holder_id])
    actors = {r.actor_id for r in shown if r.actor_id}
    names = {a: people.name_by_object_id(db, _object_id_of(db, a)) for a in actors}

    return UnitPlaceResponse(
        instance_unit_id=unit.id,
        number=number,
        holder=_ref(holders[holder_id]),
        chain=[PlaceHop(object_id=h.object_id, type=h.type, name=h.name) for h in ch.hops],
        chain_truncated=ch.truncated,
        chain_cycle=ch.cycle,
        history=[
            PlaceObservation(
                id=r.id,
                holder=_ref(holders[r.holder_object_id]),
                source=r.source,
                actor_name=names.get(r.actor_id),
                created_at=r.created_at,
            ) for r in shown
        ],
        history_truncated=len(rows) > HISTORY_LIMIT,
    )


def _object_id_of(db: Session, user_id: int) -> int | None:
    row = db.query(UserProfile.object_id).filter(UserProfile.id == user_id).first()
    return row[0] if row else None


@router.get("/holder/{object_id}", response_model=HolderContents)
def what_lies_here(object_id: int, limit: int = Query(60, ge=1, le=200),
                   offset: int = Query(0, ge=0), db: Session = Depends(get_db),
                   _: UserProfile = Depends(require_employee)):
    """**Was liegt hier?** Die Stücke, deren letzte Beobachtung auf diese Nummer zeigt.

    Seitenweise, mit Gesamtzahl daneben. Ein Halter, den es nicht gibt, wird als solcher
    zurückgegeben (``type = null``) statt als leere Liste – sonst sähe ein Tippfehler
    aus wie ein leeres Regal.
    """
    holder = places.resolve_holder(db, object_id)
    units, total = places.contents(db, object_id, limit=limit, offset=offset)

    instances = {i.id: i for i in db.query(Instance).filter(
        Instance.id.in_({u.instance_id for u in units})).all()} if units else {}
    articles = {a.id: a for a in db.query(Article).filter(
        Article.id.in_({i.article_id for i in instances.values()})).all()} if instances else {}

    out = []
    for u in units:
        inst = instances.get(u.instance_id)
        art = articles.get(inst.article_id) if inst else None
        out.append(HeldUnit(
            instance_unit_id=u.id,
            number=inst_svc.unit_number(inst, u) if inst else str(u.id),
            instance_object_id=inst.object_id if inst else 0,
            article_name=art.name if art else None,
            status=u.status,
        ))
    return HolderContents(holder=_ref(holder), units=out, total=total)
