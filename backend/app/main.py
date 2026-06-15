from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import inspect, text

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models import UserProfile
from .routers import (
    admin, article_process, articles, auth, contact, erp, health,
    orders, purchase_orders, storage_locations,
)

settings = get_settings()


def _bootstrap_admin() -> None:
    """Ensure initial_admin_email always has admin role; fall back to first user."""
    db = SessionLocal()
    try:
        if settings.initial_admin_email:
            candidate = db.query(UserProfile).filter(
                UserProfile.email == settings.initial_admin_email,
                UserProfile.is_active == True,
            ).first()
            if candidate:
                if candidate.role != "admin":
                    candidate.role = "admin"
                    db.commit()
                    print(f"INFO: Promoted {settings.initial_admin_email} to admin.", flush=True)
                return

        has_admin = db.query(UserProfile).filter(
            UserProfile.role == "admin", UserProfile.is_active == True
        ).first()
        if has_admin:
            return
        candidate = (
            db.query(UserProfile)
            .filter(UserProfile.is_active == True)
            .order_by(UserProfile.id)
            .first()
        )
        if candidate:
            candidate.role = "admin"
            db.commit()
    finally:
        db.close()


# Spalten, die nach dem Initial-Schema ergänzt wurden (Tabelle, Spalte, DDL-Typ).
# create_all() legt nur fehlende TABELLEN an – KEINE neuen Spalten auf bestehenden.
_COLUMN_SAFETY_NET = (
    ("company_settings", "google_maps_api_key", "VARCHAR(255)"),
    ("articles", "landed_unit_cost", "NUMERIC(12,4)"),
    ("orders", "article_id", "BIGINT"),
    ("orders", "quantity", "INTEGER"),
    ("orders", "desired_delivery_date", "DATE"),
)


def _ensure_columns() -> None:
    """Fehlende Spalten idempotent ergänzen, falls eine Migration nicht lief.
    create_all() ergänzt nur Tabellen, nicht Spalten auf bestehenden Tabellen."""
    try:
        with engine.connect() as conn:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            for table, col, ddl in _COLUMN_SAFETY_NET:
                if table not in tables:
                    continue
                if col not in {c["name"] for c in insp.get_columns(table)}:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"
                    ))
            conn.commit()
    except Exception as e:
        print(f"WARNING: _ensure_columns() failed: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Safety-Net: fehlende Tabellen idempotent anlegen, falls eine Migration
        # übersprungen wurde oder fehlschlug. create_all() ändert bestehende
        # Tabellen NICHT – Schema-Änderungen bleiben Sache von Alembic.
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"WARNING: create_all() failed: {e}", flush=True)
    _ensure_columns()
    try:
        _bootstrap_admin()
    except Exception as e:
        print(f"WARNING: _bootstrap_admin() failed: {e}", flush=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(erp.router)
app.include_router(articles.router)
app.include_router(article_process.router)
app.include_router(orders.router)
app.include_router(purchase_orders.router)
app.include_router(storage_locations.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
