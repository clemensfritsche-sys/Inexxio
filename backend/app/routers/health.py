from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "version": "1.0.0"}
    except Exception as e:
        # FIX: DB-Fehlertext (kann Host/Port/User der DATABASE_URL enthalten) nur noch
        # loggen statt ihn unauthentifiziert in der Antwort offenzulegen.
        print(f"WARNING: health check DB error: {e}", flush=True)
        return {"status": "unhealthy", "database": "disconnected"}
