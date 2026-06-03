"""Service layer for universal object management."""

from sqlalchemy.orm import Session

from ..models.objects import ObjectType, UniversalObject


def create_object(db: Session, obj_type: ObjectType, user_id: int) -> UniversalObject:
    """Create a new universal object record and flush to obtain the generated ID."""
    obj = UniversalObject(
        object_type=obj_type.value,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(obj)
    db.flush()
    return obj


def deactivate_object(db: Session, object_id: int, user_id: int) -> bool:
    """Soft-delete a universal object by setting is_active=False."""
    obj = db.query(UniversalObject).filter(UniversalObject.id == object_id).first()
    if not obj:
        return False
    obj.is_active = False
    obj.updated_by = user_id
    db.flush()
    return True
