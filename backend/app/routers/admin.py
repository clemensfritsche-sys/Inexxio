from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_employee
from ..core.database import get_db
from ..models import AuditLog, UserProfile
from ..schemas.admin import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    OperatingCostsResponse,
    UserProfileResponse,
    UserRoleUpdate,
)
from ..services.admin import get_or_create_settings, log_audit
from ..services.operating_costs import operating_costs

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _mask_iban(value: str | None) -> str | None:
    if not value or len(value) < 8:
        return value
    return value[:4] + " **** **** **** " + value[-4:]


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=CompanySettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    s = get_or_create_settings(db)
    resp = CompanySettingsResponse.model_validate(s)
    resp.iban_masked = _mask_iban(s.iban_encrypted)
    resp.qr_iban_masked = _mask_iban(s.qr_iban_encrypted)
    return resp


@router.patch("/settings", response_model=CompanySettingsResponse)
async def update_settings(
    data: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    s = get_or_create_settings(db)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "iban":
            s.iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", current_user.id)
        elif key == "qr_iban":
            s.qr_iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", current_user.id)
        else:
            setattr(s, key, value)
            log_audit(db, "company_settings", key, str(value), current_user.id)
    db.commit()
    db.refresh(s)
    resp = CompanySettingsResponse.model_validate(s)
    resp.iban_masked = _mask_iban(s.iban_encrypted)
    resp.qr_iban_masked = _mask_iban(s.qr_iban_encrypted)
    return resp


@router.get("/settings/public")
async def get_public_settings(db: Session = Depends(get_db)):
    """No auth — used by Impressum, AGB, Datenschutz pages."""
    from ..models.admin import CompanySettings
    s = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    if not s:
        return {"company_name": "Inexxio AG", "legal_form": "AG", "email": "info@inexxio.com",
                "website": "https://inexxio.com", "country": "Schweiz"}
    return {
        "object_id": s.object_id,
        "company_name": s.company_name, "legal_form": s.legal_form,
        "street": s.street, "street_nr": s.street_nr, "zip_code": s.zip_code,
        "city": s.city, "country": s.country, "uid_number": s.uid_number,
        "vat_number": s.vat_number, "trade_register_nr": s.trade_register_nr,
        "trade_register_canton": s.trade_register_canton, "share_capital": s.share_capital,
        "email": s.email, "phone": s.phone, "website": s.website,
        "google_maps_api_key": s.google_maps_api_key,
    }


@router.get("/operating-costs", response_model=OperatingCostsResponse)
async def get_operating_costs(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    """Betriebskosten des laufenden Monats bis heute – tatsächliche KI-/Zahlungskosten
    (aus Event-Strom bzw. Stripe-Verkäufen) + Infrastruktur-Schätzung + Hochrechnung."""
    return operating_costs(db)


# ─── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserProfileResponse])
async def list_users(
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_employee),
):
    return [UserProfileResponse.model_validate(u) for u in
            db.query(UserProfile).order_by(UserProfile.email).all()]


@router.patch("/users/{user_id}/role", response_model=UserProfileResponse)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    # Rollen-Whitelist erzwingt das Schema (Literal ``Role``) – ungültige Werte enden als 422.
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    # Die System-KI (role='ai', ADR 004) ist kein verwaltbarer Mensch: Rolle fix.
    if user.role == "ai":
        raise HTTPException(409, detail="Die System-KI-Identität kann keine andere Rolle erhalten")
    log_audit(db, "user_profiles", "role", data.role, current_user.id,
              object_id=user_id, old_value=user.role)
    user.role = data.role
    db.commit()
    db.refresh(user)
    return UserProfileResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(400, detail="Cannot deactivate yourself")
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if user.role == "ai":
        raise HTTPException(409, detail="Die System-KI kann nicht deaktiviert werden (Abschalten via KI-Konfiguration)")
    # Deadlock-Schutz: hat der Benutzer noch OFFENE Dokument-Freigaben (pending/rejected
    # Signoffs auf ausgestellten, nicht abgeschlossenen Dokumenten), würde seine
    # Deaktivierung diese Aufträge dauerhaft blockieren – nur die benannte Person darf
    # unterschreiben, und eine deaktivierte kann sich nie mehr anmelden. Erst die
    # Unterschriften klären (signieren / Ausstellung zurücknehmen), dann deaktivieren.
    if user.object_id is not None:
        from ..models import Document, DocumentSignoff
        blocking = (
            db.query(DocumentSignoff.id)
            .join(Document, DocumentSignoff.document_id == Document.id)
            .filter(DocumentSignoff.signer_object_id == user.object_id,
                    DocumentSignoff.is_active == True,
                    DocumentSignoff.status.in_(("pending", "rejected")),
                    Document.is_active == True, Document.issued == True,
                    Document.done == False)
            .count()
        )
        if blocking:
            raise HTTPException(
                409,
                detail=f"Benutzer hat noch {blocking} offene Dokument-Freigabe(n) "
                       "(Unterschrift/Bestätigung ausstehend) – zuerst klären (signieren oder "
                       "die Ausstellung zurücknehmen), sonst blockieren diese Aufträge für immer.",
            )
    log_audit(db, "user_profiles", "is_active", "false", current_user.id,
              object_id=user_id, old_value="true")
    user.is_active = False
    db.commit()
    return {"deactivated": True}


# ─── Audit log ────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    table_name: str | None = Query(None),
    db: Session = Depends(get_db),
    _: UserProfile = Depends(require_admin),
):
    q = db.query(AuditLog)
    if table_name:
        q = q.filter(AuditLog.table_name == table_name)
    total = q.count()
    logs = q.order_by(AuditLog.changed_at_utc.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"id": l.id, "object_id": l.object_id, "table_name": l.table_name,
             "field_name": l.field_name, "old_value": l.old_value, "new_value": l.new_value,
             "user_id": l.user_id, "changed_at_utc": l.changed_at_utc}
            for l in logs
        ],
    }
