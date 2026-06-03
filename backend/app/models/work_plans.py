import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin


class StepType(str, enum.Enum):
    OPERATION = "operation"
    QC_CHECK = "qc_check"


class WorkPlan(Base, TimestampMixin):
    __tablename__ = "work_plans"

    id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("objects.id"), primary_key=True
    )
    item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    steps: Mapped[list["WorkPlanStep"]] = relationship(
        "WorkPlanStep",
        back_populates="work_plan",
        cascade="all, delete-orphan",
        order_by="WorkPlanStep.step_nr",
    )


class WorkPlanStep(Base):
    __tablename__ = "work_plan_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    work_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_plans.id"), nullable=False, index=True
    )
    step_nr: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(
        String(20), default=StepType.OPERATION, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    setup_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    exec_min_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    nominal_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    tolerance: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    work_plan: Mapped["WorkPlan"] = relationship("WorkPlan", back_populates="steps")
