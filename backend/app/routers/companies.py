from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.auth import require_staff
from ..core.database import get_db
from ..models.audit import AuditLog, UserProfile
from ..models.companies import Company, Contact
from ..models.objects import ObjectType, UniversalObject
from ..schemas.companies import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    ContactCreate,
    ContactResponse,
    ContactUpdate,
)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    q: Optional[str] = Query(None),
    company_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    query = db.query(Company).filter(Company.is_active == True)
    if q:
        query = query.filter(Company.name.ilike(f"%{q}%"))
    if company_type:
        query = query.filter(Company.company_type == company_type)
    return [
        CompanyResponse.model_validate(c)
        for c in query.order_by(Company.name).limit(200).all()
    ]


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = UniversalObject(
        object_type=ObjectType.COMPANY,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    address_dict = data.address.model_dump() if data.address else None
    company = Company(
        id=obj.id,
        name=data.name,
        company_type=data.company_type,
        uid=data.uid,
        vat_id=data.vat_id,
        address=address_dict,
        country_code=data.country_code,
        iban=data.iban,
        payment_term_days=data.payment_term_days,
        notes=data.notes,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.is_active == True)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.is_active == True)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "address" and value is not None:
            company.address = value if isinstance(value, dict) else value.model_dump()
        else:
            setattr(company, key, value)

        audit = AuditLog(
            object_id=company_id,
            table_name="companies",
            field_name=key,
            new_value=str(value),
            user_id=current_user.id,
        )
        db.add(audit)

    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.is_active == True)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.is_active = False
    db.commit()


@router.post(
    "/{company_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    company_id: int,
    data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    obj = UniversalObject(
        object_type=ObjectType.CONTACT,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(obj)
    db.flush()

    contact = Contact(id=obj.id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.get("/{company_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    contacts = (
        db.query(Contact)
        .filter(Contact.company_id == company_id, Contact.is_active == True)
        .all()
    )
    return [ContactResponse.model_validate(c) for c in contacts]


@router.patch(
    "/{company_id}/contacts/{contact_id}", response_model=ContactResponse
)
async def update_contact(
    company_id: int,
    contact_id: int,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    contact = (
        db.query(Contact)
        .filter(
            Contact.id == contact_id,
            Contact.company_id == company_id,
            Contact.is_active == True,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(contact, key, value)

    db.commit()
    db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.delete(
    "/{company_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def deactivate_contact(
    company_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    contact = (
        db.query(Contact)
        .filter(
            Contact.id == contact_id,
            Contact.company_id == company_id,
            Contact.is_active == True,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.is_active = False
    db.commit()
