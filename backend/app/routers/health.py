from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "version": get_settings().app_version}
    except Exception as e:
        # Der DB-Fehlertext kann Host/Port/User der DATABASE_URL enthalten – nur loggen,
        # nie unauthentifiziert in der Antwort zeigen.
        print(f"WARNING: health check DB error: {e}", flush=True)
        return {"status": "unhealthy", "database": "disconnected"}
