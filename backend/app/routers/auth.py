from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.admin import AddressIn, UserProfileResponse, UserProfileUpdate
from ..services import address_book, people

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    data: UserProfileUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Selbstbedienung auf die EIGENEN Daten – derselbe Datensatz, derselbe Schreibpfad
    # wie am ERP-Benutzer-Datensatz (inkl. Audit-Log; Akteur ist die Person selbst).
    people.apply_profile_update(db, current_user, data, current_user.id, staff=False)
    db.commit()
    db.refresh(current_user)
    return current_user


# ─── Das Adressbuch – dieselben Funktionen wie am ERP-Datensatz ──────────────────

@router.post("/me/addresses", response_model=UserProfileResponse)
async def add_my_address(
    data: AddressIn,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address_book.add(db, current_user, data.model_dump(exclude_unset=True), current_user.id)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/addresses/{address_id}", response_model=UserProfileResponse)
async def change_my_address(
    address_id: int,
    data: AddressIn,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address_book.change(db, current_user, address_id, data.model_dump(exclude_unset=True),
                        current_user.id)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me/addresses/{address_id}", response_model=UserProfileResponse)
async def remove_my_address(
    address_id: int,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    address_book.remove(db, current_user, address_id, current_user.id)
    db.commit()
    db.refresh(current_user)
    return current_user

