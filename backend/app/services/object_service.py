"""
Creates entries in the 'objects' table and returns the new 9-digit ID.
All ERP entities must go through here to get their unique ID.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.base_object import Object, ObjectType


async def create_object(
    db: AsyncSession,
    object_type: ObjectType,
    created_by: int | None = None,
) -> int:
    obj = Object(object_type=object_type, created_by=created_by)
    db.add(obj)
    await db.flush()
    return obj.id


async def soft_delete(db: AsyncSession, object_id: int) -> None:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if obj:
        obj.is_active = False
