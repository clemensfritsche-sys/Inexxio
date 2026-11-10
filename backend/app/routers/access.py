"""►►► **Der Zugang einer Person am ERP-Datensatz** – Passkeys und Verbindungen mit Claude. ◄◄◄

**ERP ist Master:** was die Person im Konto unter «Sicherheit» sieht und trennt, sieht und trennt
hier sie selbst oder der Admin (``policy`` «person.access») – mit **denselben Diensten**
(``passkey.list_passkeys`` · ``delete_passkey``, ``mcp.grants`` · ``revoke``), die auch das Konto
ruft (``routers/passkey``, ``routers/mcp``). Einen Passkey **einrichten** kann nur die Person auf
ihrem Gerät (``policy.SELF_SERVICE``).

Kein Handgriff: Anmeldewege fasst die KI nicht an (``handgriff._routes`` lässt diesen Router aus).
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import DB
from ..domain import policy
from ..domain.errors import NotFound
from ..models import UserProfile
from ..schemas.mcp import GrantOut
from ..schemas.passkey import PasskeyResponse
from ..services import mcp, passkey

router = APIRouter(prefix="/api/v1/erp/records/{object_id}", tags=["erp"])


def _person(db: Session, object_id: int, viewer: UserProfile) -> UserProfile:
    """Die Person – und das Tor: ihren Zugang sieht und ändert nur sie selbst oder der Admin."""
    person = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    if person is None:
        raise NotFound(f"Person «{object_id}» gibt es nicht.")
    policy.require(viewer, "person.access", person.object_id)
    return person


@router.get("/passkeys", response_model=list[PasskeyResponse])
def record_passkeys(object_id: int, db: Session = DB,
                    viewer: UserProfile = Depends(require_employee)):
    """Die Passkeys einer Person (nur sie selbst oder der Admin)."""
    return passkey.list_passkeys(db, _person(db, object_id, viewer))


@router.delete("/passkeys/{passkey_id}", status_code=204)
def remove_record_passkey(object_id: int, passkey_id: int, db: Session = DB,
                          viewer: UserProfile = Depends(require_employee)):
    """Einen Passkey einer Person entfernen – sie meldet sich danach anders an."""
    passkey.delete_passkey(db, _person(db, object_id, viewer), passkey_id)
    return Response(status_code=204)


@router.get("/mcp", response_model=list[GrantOut])
def record_grants(object_id: int, db: Session = DB,
                  viewer: UserProfile = Depends(require_employee)):
    """Die offenen Verbindungen einer Person mit Claude (nur sie selbst oder der Admin)."""
    return mcp.grants(db, _person(db, object_id, viewer))


@router.post("/mcp/{grant_id}/revoke", response_model=list[GrantOut])
def revoke_record_grant(object_id: int, grant_id: int, db: Session = DB,
                        viewer: UserProfile = Depends(require_employee)):
    """Eine Verbindung einer Person mit Claude trennen – ab sofort kommt dieser Client nicht mehr hinein."""
    person = _person(db, object_id, viewer)
    mcp.revoke(db, person, grant_id)
    db.flush()
    return mcp.grants(db, person)
