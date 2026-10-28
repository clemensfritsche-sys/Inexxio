from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db

router = APIRouter(tags=["health"])


@lru_cache(maxsize=1)
def migration_head() -> str:
    """Die höchste Revision in ``alembic/versions`` – der Stand, auf dem die Datenbank stehen
    muss. Einmal gelesen: der Code ändert sich nicht, solange der Dienst läuft."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head() or ""


def schema_state(db: Session) -> dict:
    """►►► **Steht die Datenbank auf dem Stand dieses Codes?** ◄◄◄ Scheitert ``alembic upgrade
    head`` beim Start, läuft der Dienst trotzdem (die Netze tragen) – das darf nie unbemerkt
    bleiben: der Deploy liest diese Auskunft und wird rot (``deploy-*.yml``)."""
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar() or ""
    except Exception:
        db.rollback()
        revision = ""
    head = migration_head()
    return {"schema": "current" if revision and revision == head else "behind",
            "revision": revision, "head": head}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected", "version": get_settings().app_version,
                **schema_state(db)}
    except Exception as e:
        # Der DB-Fehlertext kann Host/Port/User der DATABASE_URL enthalten – nur loggen,
        # nie unauthentifiziert in der Antwort zeigen.
        print(f"WARNING: health check DB error: {e}", flush=True)
        return {"status": "unhealthy", "database": "disconnected"}
