from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import get_current_user, require_admin, require_employee
from ..core.database import get_db
from ..models.audit import AuditLog, Notification, UserProfile
from ..schemas.admin import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    UserProfileResponse,
    UserRoleUpdate,
)
from ..services.admin import get_or_create_settings, log_audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_ROLES = {"admin", "employee", "supplier", "customer"}


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
        "company_name": s.company_name, "legal_form": s.legal_form,
        "street": s.street, "street_nr": s.street_nr, "zip_code": s.zip_code,
        "city": s.city, "country": s.country, "uid_number": s.uid_number,
        "vat_number": s.vat_number, "trade_register_nr": s.trade_register_nr,
        "trade_register_canton": s.trade_register_canton, "share_capital": s.share_capital,
        "email": s.email, "phone": s.phone, "website": s.website,
    }


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
    if data.role not in VALID_ROLES:
        raise HTTPException(400, detail=f"Invalid role. Must be one of: {VALID_ROLES}")
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
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


# ─── Notifications ────────────────────────────────────────────────────────────

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    notifications = q.order_by(Notification.created_at_utc.desc()).limit(50).all()
    return [
        {"id": n.id, "type": n.type, "title": n.title, "message": n.message,
         "link": n.link, "is_read": n.is_read, "created_at_utc": n.created_at_utc}
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"marked_read": True}
