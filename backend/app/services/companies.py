"""Service layer for company and contact operations."""

from typing import Optional

from sqlalchemy.orm import Session

from ..models.companies import Company, Contact


def get_company(
    db: Session, company_id: int, active_only: bool = True
) -> Optional[Company]:
    """Fetch a single company by ID."""
    query = db.query(Company).filter(Company.id == company_id)
    if active_only:
        query = query.filter(Company.is_active == True)
    return query.first()


def get_primary_contact(db: Session, company_id: int) -> Optional[Contact]:
    """Return the primary contact for a company, or the first active contact if none is marked."""
    primary = (
        db.query(Contact)
        .filter(
            Contact.company_id == company_id,
            Contact.is_active == True,
            Contact.is_primary == True,
        )
        .first()
    )
    if primary:
        return primary
    return (
        db.query(Contact)
        .filter(Contact.company_id == company_id, Contact.is_active == True)
        .first()
    )


def set_primary_contact(db: Session, company_id: int, contact_id: int) -> bool:
    """Ensure only one contact is marked as primary for the company."""
    # Clear existing primary flag
    db.query(Contact).filter(
        Contact.company_id == company_id, Contact.is_primary == True
    ).update({"is_primary": False})

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
        return False
    contact.is_primary = True
    db.flush()
    return True
