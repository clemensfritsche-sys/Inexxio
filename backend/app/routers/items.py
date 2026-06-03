from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user, get_admin_user
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse
from app.schemas.common import PaginatedResponse
from app.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    data: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await item_service.create_item(db, data, created_by=current_user.id)


@router.get("/", response_model=PaginatedResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items, total = await item_service.list_items(db, page, page_size, category, search)
    return PaginatedResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = await item_service.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    data: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = await item_service.update_item(db, item_id, data, updated_by=current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/{item_id}/approve", response_model=ItemResponse)
async def approve_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    item = await item_service.approve_item(db, item_id, approved_by=current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/{item_id}/replace", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def replace_item(
    item_id: int,
    data: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    new_item = await item_service.replace_item(db, item_id, data, created_by=current_user.id)
    if not new_item:
        raise HTTPException(status_code=404, detail="Item not found")
    return new_item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_admin_user),
):
    from app.services.object_service import soft_delete
    await soft_delete(db, item_id)
    await db.commit()
