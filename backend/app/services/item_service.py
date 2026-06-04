from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.item import Item
from app.models.base_object import Object, ObjectType
from app.models.audit_log import AuditLog
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.object_service import create_object


async def create_item(db: AsyncSession, data: ItemCreate, created_by: int | None = None) -> Item:
    obj_id = await create_object(db, ObjectType.item, created_by=created_by)
    item = Item(id=obj_id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_item(db: AsyncSession, item_id: int) -> Item | None:
    result = await db.execute(
        select(Item).where(Item.id == item_id)
    )
    return result.scalar_one_or_none()


async def list_items(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    search: str | None = None,
    active_only: bool = True,
) -> tuple[list[Item], int]:
    query = select(Item)
    count_query = select(func.count()).select_from(Item)

    if active_only:
        # Join objects to check is_active
        query = query.join(Object, Item.id == Object.id).where(Object.is_active == True)
        count_query = count_query.join(Object, Item.id == Object.id).where(Object.is_active == True)

    if category:
        query = query.where(Item.category == category)
        count_query = count_query.where(Item.category == category)

    if search:
        query = query.where(Item.name.ilike(f"%{search}%"))
        count_query = count_query.where(Item.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return result.scalars().all(), total


async def update_item(
    db: AsyncSession, item_id: int, data: ItemUpdate, updated_by: int | None = None
) -> Item | None:
    item = await get_item(db, item_id)
    if not item:
        return None

    updates = data.model_dump(exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(item, field)
        if old_value != new_value:
            log = AuditLog(
                object_id=item_id,
                table_name="items",
                field_name=field,
                old_value=str(old_value),
                new_value=str(new_value),
                user_id=updated_by,
            )
            db.add(log)
        setattr(item, field, new_value)

    await db.commit()
    await db.refresh(item)
    return item


async def approve_item(db: AsyncSession, item_id: int, approved_by: int) -> Item | None:
    from datetime import datetime, timezone
    item = await get_item(db, item_id)
    if not item:
        return None
    item.is_approved = True
    item.approved_by = approved_by
    item.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item


async def replace_item(
    db: AsyncSession, old_item_id: int, new_data: ItemCreate, created_by: int | None = None
) -> Item | None:
    old_item = await get_item(db, old_item_id)
    if not old_item:
        return None

    new_item = await create_item(db, new_data, created_by=created_by)
    new_item.replaces_id = old_item_id
    old_item.replaced_by_id = new_item.id
    await db.commit()
    return new_item
