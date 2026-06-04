import enum
from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BOM(Base):
    __tablename__ = "boms"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    parent_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=True)


class BOMLine(Base):
    __tablename__ = "bom_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("boms.id"), nullable=False, index=True)
    component_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="Stk", nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=True)


class WorkPlan(Base):
    __tablename__ = "work_plans"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("items.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class StepType(str, enum.Enum):
    operation = "operation"
    qc_check = "qc_check"


class WorkPlanStep(Base):
    __tablename__ = "work_plan_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("work_plans.id"), nullable=False, index=True)
    step_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[StepType] = mapped_column(Enum(StepType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=True)
    setup_min: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    exec_min_per_unit: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    nominal_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    tolerance: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
