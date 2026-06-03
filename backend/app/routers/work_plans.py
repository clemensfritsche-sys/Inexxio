from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import UserProfile
from ..models.objects import ObjectType, UniversalObject
from ..models.work_plans import WorkPlan, WorkPlanStep
from ..schemas.work_plans import WorkPlanCreate, WorkPlanResponse, WorkPlanUpdate

router = APIRouter(prefix="/api/v1/work-plans", tags=["work-plans"])


@router.get("")
async def list_work_plans(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    plans = (
        db.query(WorkPlan)
        .filter(WorkPlan.is_active == True)
        .order_by(WorkPlan.updated_at.desc())
        .limit(100)
        .all()
    )
    return [WorkPlanResponse.model_validate(p) for p in plans]


@router.post("", response_model=WorkPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_work_plan(
    data: WorkPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = UniversalObject(
        object_type=ObjectType.WORK_PLAN,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    plan = WorkPlan(
        id=obj.id,
        item_id=data.item_id,
        name=data.name,
        description=data.description,
    )
    db.add(plan)
    db.flush()

    for step_data in data.steps:
        step = WorkPlanStep(work_plan_id=plan.id, **step_data.model_dump())
        db.add(step)

    db.commit()
    db.refresh(plan)
    return WorkPlanResponse.model_validate(plan)


@router.get("/{plan_id}", response_model=WorkPlanResponse)
async def get_work_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    plan = (
        db.query(WorkPlan)
        .filter(WorkPlan.id == plan_id, WorkPlan.is_active == True)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Work plan not found")
    return WorkPlanResponse.model_validate(plan)


@router.patch("/{plan_id}", response_model=WorkPlanResponse)
async def update_work_plan(
    plan_id: int,
    data: WorkPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    plan = (
        db.query(WorkPlan)
        .filter(WorkPlan.id == plan_id, WorkPlan.is_active == True)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Work plan not found")

    if data.item_id is not None:
        plan.item_id = data.item_id
    if data.name is not None:
        plan.name = data.name
    if data.description is not None:
        plan.description = data.description

    if data.steps is not None:
        for existing_step in plan.steps:
            db.delete(existing_step)
        db.flush()
        for step_data in data.steps:
            step = WorkPlanStep(work_plan_id=plan.id, **step_data.model_dump())
            db.add(step)

    db.commit()
    db.refresh(plan)
    return WorkPlanResponse.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_work_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    plan = (
        db.query(WorkPlan)
        .filter(WorkPlan.id == plan_id, WorkPlan.is_active == True)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Work plan not found")
    plan.is_active = False
    db.commit()
