import enum
from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_object import Object


class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"
    supplier = "supplier"
    customer = "customer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), primary_key=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.customer, nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    function: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="de", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Zurich", nullable=False)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=True)
    weekly_hours: Mapped[float] = mapped_column(Numeric(4, 1), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    terms_accepted_at = mapped_column(nullable=True)
    terms_version: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # shadow account = created during guest checkout, not yet activated
    is_shadow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"), nullable=True)
