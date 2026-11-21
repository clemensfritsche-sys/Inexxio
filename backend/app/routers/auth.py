from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.actor import public
from ..core.auth import get_current_user
from ..core.database import DB
from ..models import UserProfile
from ..schemas.admin import (AddressIn, EmailCheck, LoginLinkIn, LoginLinkResult,
                             UserProfileResponse, UserProfileUpdate)
from ..services import address_book, login_link, people, visitor
from ..domain.errors import Conflict

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

#: Anmeldelinks je Absender und Stunde – darüber nimmt die Oberfläche den Weg über Firebase.
LINK_LIMIT = 5


@router.post("/link", response_model=LoginLinkResult, dependencies=[public("login")])
def send_login_link(data: LoginLinkIn, request: Request, db: Session = DB) -> LoginLinkResult:
    """Den Anmeldelink im Kleid des Hauses schicken (``services/login_link``); ``sent=false``
    = nicht hinausgegangen, die Oberfläche schickt ihn über Firebase."""
    email = people.normalize_email(data.email.strip())
    if not people.is_email(email) or not visitor.allow_send("login", request, LINK_LIMIT):
        return LoginLinkResult(sent=False)
    return LoginLinkResult(sent=login_link.send(db, email, visitor.country(request)))


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: UserProfile = Depends(get_current_user)):
    """Mein Profil – die angemeldete Person."""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
def update_me(
    data: UserProfileUpdate,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = DB,
):
    """Mein Profil ändern – derselbe Weg wie im ERP (``people.apply_profile_update``), nur für die eigenen Angaben."""
    # Selbstbedienung auf die EIGENEN Daten – derselbe Datensatz, derselbe Schreibpfad
    # wie am ERP-Benutzer-Datensatz (inkl. Audit-Log; Akteur ist die Person selbst).
    people.apply_profile_update(db, current_user, data, current_user.id, staff=False)
    db.flush()
    db.refresh(current_user)
    return current_user


@router.post("/me/email-check", status_code=204)
def check_my_email(
    data: EmailCheck,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = DB,
):
    """Darf die Anmelde-E-Mail auf diese Adresse wechseln? – gefragt, BEVOR Firebase den
    Bestätigungslink schickt (``people.email_problem``). 204 = ja, sonst 409 mit Grund."""
    problem = people.email_problem(db, current_user, data.email)
    if problem:
        raise Conflict(problem)


# ─── Das Adressbuch – dieselben Funktionen wie am ERP-Datensatz ──────────────────

@router.post("/me/addresses", response_model=UserProfileResponse)
def add_my_address(
    data: AddressIn,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = DB,
):
    """Eine Anschrift in mein Adressbuch aufnehmen."""
    address_book.add(db, current_user, data.model_dump(exclude_unset=True), current_user.id)
    db.flush()
    db.refresh(current_user)
    return current_user


@router.patch("/me/addresses/{address_id}", response_model=UserProfileResponse)
def change_my_address(
    address_id: int,
    data: AddressIn,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = DB,
):
    """Eine Anschrift in meinem Adressbuch ändern."""
    address_book.change(db, current_user, address_id, data.model_dump(exclude_unset=True),
                        current_user.id)
    db.flush()
    db.refresh(current_user)
    return current_user


@router.delete("/me/addresses/{address_id}", response_model=UserProfileResponse)
def remove_my_address(
    address_id: int,
    current_user: UserProfile = Depends(get_current_user),
    db: Session = DB,
):
    """Eine Anschrift aus meinem Adressbuch entfernen."""
    address_book.remove(db, current_user, address_id, current_user.id)
    db.flush()
    db.refresh(current_user)
    return current_user

