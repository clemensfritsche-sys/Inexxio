from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..models import UserProfile

router = APIRouter(tags=["health"])
settings = get_settings()

TARGET = "clemens.fritsche@gmail.com"


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "version": "1.0.0"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.get("/api/v1/debug")
async def debug(db: Session = Depends(get_db)):
    admins = db.query(UserProfile).filter(
        UserProfile.role == "admin", UserProfile.is_active == True
    ).all()
    target = db.query(UserProfile).filter(
        UserProfile.email == TARGET, UserProfile.is_active == True
    ).first()
    total = db.query(UserProfile).filter(UserProfile.is_active == True).count()
    return {
        "initial_admin_email_config": settings.initial_admin_email,
        "total_active_users": total,
        "admin_count": len(admins),
        "admins": [{"id": u.id, "email": u.email} for u in admins],
        "target_user": {
            "exists": target is not None,
            "role": target.role if target else None,
            "firebase_uid": target.firebase_uid[:8] + "..." if target else None,
        },
    }
