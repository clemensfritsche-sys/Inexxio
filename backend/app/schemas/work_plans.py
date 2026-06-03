from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkPlanStepCreate(BaseModel):
    step_nr: int
    step_type: str = "operation"
    name: str
    resource: Optional[str] = None
    setup_min: Optional[Decimal] = None
    exec_min_per_unit: Optional[Decimal] = None
    nominal_value: Optional[Decimal] = None
    tolerance: Optional[Decimal] = None
    unit: Optional[str] = None
    is_mandatory: bool = True


class WorkPlanCreate(BaseModel):
    item_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    steps: list[WorkPlanStepCreate] = []


class WorkPlanUpdate(BaseModel):
    item_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[list[WorkPlanStepCreate]] = None


class WorkPlanStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_nr: int
    step_type: str
    name: str
    resource: Optional[str]
    setup_min: Optional[Decimal]
    exec_min_per_unit: Optional[Decimal]
    nominal_value: Optional[Decimal]
    tolerance: Optional[Decimal]
    unit: Optional[str]
    is_mandatory: bool


class WorkPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: Optional[int]
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    steps: list[WorkPlanStepResponse] = []
