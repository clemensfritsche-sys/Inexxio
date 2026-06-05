from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.auth import require_admin, require_employee, require_staff
from ..core.database import get_db
from ..models.admin import CompanySettings
from ..models.audit import AuditLog, UserProfile
from ..models.item_config import ItemCategory, ItemName, ItemSurface
from ..schemas.admin import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    UserProfileResponse,
    UserRoleUpdate,
)
from ..schemas.item_config import (
    ItemCategoryCreate,
    ItemCategoryResponse,
    ItemNameCreate,
    ItemNameResponse,
    ItemSurfaceCreate,
    ItemSurfaceResponse,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

VALID_ROLES = {"admin", "employee", "supplier", "customer"}


def _mask_iban(iban: str | None) -> str | None:
    if not iban or len(iban) < 8:
        return iban
    return iban[:4] + " **** **** **** " + iban[-4:]


def _get_or_create_settings(db: Session) -> CompanySettings:
    settings_obj = (
        db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    )
    if not settings_obj:
        settings_obj = CompanySettings(id=1)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return settings_obj


@router.get("/settings", response_model=CompanySettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    settings_obj = _get_or_create_settings(db)
    response = CompanySettingsResponse.model_validate(settings_obj)
    response.iban_masked = _mask_iban(settings_obj.iban_encrypted)
    response.qr_iban_masked = _mask_iban(settings_obj.qr_iban_encrypted)
    return response


@router.patch("/settings", response_model=CompanySettingsResponse)
async def update_settings(
    data: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    settings_obj = _get_or_create_settings(db)

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "iban":
            settings_obj.iban_encrypted = value
            log_value = "[UPDATED]"
        elif key == "qr_iban":
            settings_obj.qr_iban_encrypted = value
            log_value = "[UPDATED]"
        else:
            setattr(settings_obj, key, value)
            log_value = str(value)

        audit = AuditLog(
            table_name="company_settings",
            field_name=key,
            new_value=log_value,
            user_id=current_user.id,
        )
        db.add(audit)

    db.commit()
    db.refresh(settings_obj)

    response = CompanySettingsResponse.model_validate(settings_obj)
    response.iban_masked = _mask_iban(settings_obj.iban_encrypted)
    response.qr_iban_masked = _mask_iban(settings_obj.qr_iban_encrypted)
    return response


@router.get("/settings/public")
async def get_public_settings(db: Session = Depends(get_db)):
    """Public endpoint for legal pages (Impressum, AGB) — no auth required."""
    settings_obj = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    if not settings_obj:
        return {
            "company_name": "Inexxio AG",
            "legal_form": "AG",
            "email": "info@inexxio.com",
            "website": "https://inexxio.com",
            "country": "Schweiz",
        }
    return {
        "company_name": settings_obj.company_name,
        "legal_form": settings_obj.legal_form,
        "street": settings_obj.street,
        "street_nr": settings_obj.street_nr,
        "zip_code": settings_obj.zip_code,
        "city": settings_obj.city,
        "country": settings_obj.country,
        "uid_number": settings_obj.uid_number,
        "vat_number": settings_obj.vat_number,
        "trade_register_nr": settings_obj.trade_register_nr,
        "trade_register_canton": settings_obj.trade_register_canton,
        "share_capital": settings_obj.share_capital,
        "email": settings_obj.email,
        "phone": settings_obj.phone,
        "website": settings_obj.website,
    }


@router.get("/users", response_model=list[UserProfileResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_employee),
):
    users = db.query(UserProfile).order_by(UserProfile.email).all()
    return [UserProfileResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}/role", response_model=UserProfileResponse)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    if data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400, detail=f"Invalid role. Must be one of: {VALID_ROLES}"
        )
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audit = AuditLog(
        object_id=user_id,
        table_name="user_profiles",
        field_name="role",
        old_value=user.role,
        new_value=data.role,
        user_id=current_user.id,
    )
    db.add(audit)
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
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audit = AuditLog(
        object_id=user_id,
        table_name="user_profiles",
        field_name="is_active",
        old_value="true",
        new_value="false",
        user_id=current_user.id,
    )
    db.add(audit)
    user.is_active = False
    db.commit()
    return {"deactivated": True}


@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    table_name: str = Query(None),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_admin),
):
    query = db.query(AuditLog)
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)

    total = query.count()
    logs = (
        query.order_by(AuditLog.changed_at_utc.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "object_id": log.object_id,
                "table_name": log.table_name,
                "field_name": log.field_name,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "user_id": log.user_id,
                "changed_at_utc": log.changed_at_utc,
            }
            for log in logs
        ],
    }


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    from ..models.audit import Notification

    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    notifications = (
        query.order_by(Notification.created_at_utc.desc()).limit(50).all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "created_at_utc": n.created_at_utc,
        }
        for n in notifications
    ]


@router.get("/item-names", response_model=list[ItemNameResponse])
async def list_item_names(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    return [ItemNameResponse.model_validate(n) for n in db.query(ItemName).filter(ItemName.is_active == True).order_by(ItemName.label).all()]


@router.post("/item-names", response_model=ItemNameResponse, status_code=201)
async def create_item_name(
    data: ItemNameCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    existing = db.query(ItemName).filter(ItemName.label == data.label).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Label already exists")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return ItemNameResponse.model_validate(existing)
    obj = ItemName(label=data.label, created_by=current_user.id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ItemNameResponse.model_validate(obj)


@router.get("/item-surfaces", response_model=list[ItemSurfaceResponse])
async def list_item_surfaces(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    return [ItemSurfaceResponse.model_validate(s) for s in db.query(ItemSurface).filter(ItemSurface.is_active == True).order_by(ItemSurface.label).all()]


@router.post("/item-surfaces", response_model=ItemSurfaceResponse, status_code=201)
async def create_item_surface(
    data: ItemSurfaceCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    existing = db.query(ItemSurface).filter(ItemSurface.label == data.label).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Label already exists")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return ItemSurfaceResponse.model_validate(existing)
    obj = ItemSurface(label=data.label, created_by=current_user.id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ItemSurfaceResponse.model_validate(obj)


@router.get("/item-categories", response_model=list[ItemCategoryResponse])
async def list_item_categories(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    return [ItemCategoryResponse.model_validate(c) for c in db.query(ItemCategory).filter(ItemCategory.is_active == True).order_by(ItemCategory.label).all()]


@router.post("/item-categories", response_model=ItemCategoryResponse, status_code=201)
async def create_item_category(
    data: ItemCategoryCreate,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    existing = db.query(ItemCategory).filter(ItemCategory.label == data.label).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Label already exists")
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return ItemCategoryResponse.model_validate(existing)
    obj = ItemCategory(label=data.label, created_by=current_user.id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ItemCategoryResponse.model_validate(obj)


@router.delete("/item-names/{item_id}", status_code=204)
async def delete_item_name(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(ItemName).filter(ItemName.id == item_id, ItemName.is_active == True).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    obj.is_active = False
    db.commit()


@router.delete("/item-surfaces/{item_id}", status_code=204)
async def delete_item_surface(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(ItemSurface).filter(ItemSurface.id == item_id, ItemSurface.is_active == True).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    obj.is_active = False
    db.commit()


@router.delete("/item-categories/{item_id}", status_code=204)
async def delete_item_category(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    obj = db.query(ItemCategory).filter(ItemCategory.id == item_id, ItemCategory.is_active == True).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    obj.is_active = False
    db.commit()


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_staff),
):
    from ..models.audit import Notification

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"marked_read": True}
