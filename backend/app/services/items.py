"""Service layer for item operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models.audit import AuditLog
from ..models.items import Item
from ..models.objects import ObjectType, UniversalObject


def get_item(db: Session, item_id: int, active_only: bool = True) -> Optional[Item]:
    """Fetch a single item by ID."""
    query = db.query(Item).filter(Item.id == item_id)
    if active_only:
        query = query.filter(Item.is_active == True)
    return query.first()


def approve_item(db: Session, item: Item, approver_id: int) -> Item:
    """Mark an item as approved and record the approver."""
    item.is_approved = True
    item.approved_by = approver_id
    item.approved_at = datetime.now(timezone.utc)

    audit = AuditLog(
        object_id=item.id,
        table_name="items",
        field_name="is_approved",
        old_value="false",
        new_value="true",
        user_id=approver_id,
    )
    db.add(audit)
    db.flush()
    return item


def adjust_stock(
    db: Session, item: Item, delta: float, user_id: int, reason: str = ""
) -> Item:
    """Adjust the current stock of an item by a delta value (positive = in, negative = out)."""
    old_stock = float(item.current_stock)
    item.current_stock = float(item.current_stock) + delta  # type: ignore[assignment]

    audit = AuditLog(
        object_id=item.id,
        table_name="items",
        field_name="current_stock",
        old_value=str(old_stock),
        new_value=str(float(item.current_stock)),
        user_id=user_id,
    )
    db.add(audit)
    db.flush()
    return item
