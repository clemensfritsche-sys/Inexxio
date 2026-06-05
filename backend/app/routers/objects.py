from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models.audit import UserProfile

router = APIRouter(prefix="/api/v1/objects", tags=["objects"])


@router.get("")
async def list_objects(
    q: Optional[str] = Query(None, description="Search query"),
    object_type: Optional[str] = Query(None, description="Filter by object type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    queries = []
    params: dict = {"offset": offset, "limit": page_size}

    if not object_type or object_type == "item":
        item_q = """
            SELECT o.id, 'item' AS object_type, i.name AS title,
                   i.status AS status,
                   o.created_at, o.updated_at
            FROM objects o
            JOIN items i ON o.id = i.id
            WHERE o.is_active = true AND i.is_active = true
        """
        if q:
            item_q += " AND (i.name ILIKE :search OR CAST(o.id AS TEXT) ILIKE :search)"
            params["search"] = f"%{q}%"
        queries.append(item_q)

    if not object_type or object_type == "work_plan":
        wp_q = """
            SELECT o.id, 'work_plan' AS object_type, wp.name AS title,
                   'Aktiv' AS status,
                   o.created_at, o.updated_at
            FROM objects o
            JOIN work_plans wp ON o.id = wp.id
            WHERE o.is_active = true AND wp.is_active = true
        """
        if q:
            wp_q += " AND (wp.name ILIKE :search OR CAST(o.id AS TEXT) ILIKE :search)"
        queries.append(wp_q)

    if not object_type or object_type == "company":
        co_q = """
            SELECT o.id, 'company' AS object_type, c.name AS title,
                   c.company_type AS status,
                   o.created_at, o.updated_at
            FROM objects o
            JOIN companies c ON o.id = c.id
            WHERE o.is_active = true AND c.is_active = true
        """
        if q:
            co_q += " AND (c.name ILIKE :search OR CAST(o.id AS TEXT) ILIKE :search)"
        queries.append(co_q)

    if not queries:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    union_q = " UNION ALL ".join(queries)
    count_q = f"SELECT COUNT(*) FROM ({union_q}) sub"
    data_q = (
        f"SELECT * FROM ({union_q}) sub ORDER BY updated_at DESC "
        f"LIMIT :limit OFFSET :offset"
    )

    total = db.execute(text(count_q), params).scalar() or 0
    rows = db.execute(text(data_q), params).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [dict(row._mapping) for row in rows],
    }
