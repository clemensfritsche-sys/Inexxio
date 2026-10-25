"""**Die Zahlungen einer Person bzw. einer eigenen Gesellschaft** – eine Ableitung aus den
Zahlungsmodulen (``services/payment_list``)."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..services import payment_list

router = APIRouter(prefix="/api/v1/erp", tags=["erp"])


class PaymentRow(BaseModel):
    """Eine Zeile – Nummer · Art · Auftrag · Partei · Betrag ± · Stand."""
    voucher_id: int
    number: str
    kind: str
    order_object_id: Optional[int] = None
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    #: ``+`` kommt zu uns, ``−`` geht von uns.
    sign: str
    amount: Optional[str] = None
    currency: str = "CHF"
    #: ``overdue`` · ``open`` · ``paid`` · ``void``
    state: str
    state_label: str


@router.get("/payments", response_model=list[PaymentRow])
def list_payments(
    person: Optional[int] = None,
    company: Optional[int] = None,
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
) -> Any:
    """**Die Zahlungen einer Person** (``person=``) **oder einer eigenen Gesellschaft**
    (``company=``) – neueste Nummer zuoberst."""
    if (person is None) == (company is None):
        raise HTTPException(status_code=400,
                            detail="Entweder eine Person oder eine Gesellschaft angeben.")
    return (payment_list.of_person(db, person) if person is not None
            else payment_list.of_company(db, company))
