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
    orders, storage_locations,
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
    ("purchase_orders", "order_total", "NUMERIC(12,2)"),
    ("purchase_orders", "ordered_at", "TIMESTAMP WITH TIME ZONE"),
    ("article_process_steps", "shared_fields", "JSONB"),
    ("article_process_steps", "position", "INTEGER DEFAULT 1"),
    ("article_process_steps", "sample_percent", "INTEGER"),
)

# Obsolete Spalten, die aus dem Modell entfernt wurden. In Prod wird das Schema
# via create_all() (nicht Alembic) erzeugt – diese NOT-NULL/Alt-Spalten würden
# sonst INSERTs brechen (z. B. purchase_orders.transport_included). Idempotent.
_DROP_COLUMN_SAFETY_NET = (
    ("purchase_orders", "transport_cost"),
    ("purchase_orders", "transport_included"),
    ("purchase_orders", "other_costs"),
    ("purchase_orders", "rejection_reason"),
    ("purchase_orders", "object_id"),
    ("purchase_orders", "unit_price"),
    ("purchase_orders", "desired_delivery_date"),
)

# Daten-Normalisierungen (idempotent), wenn keine Alembic-Migration lief.
_DATA_FIXES = (
    "UPDATE purchase_orders SET status='ordered' WHERE status IN ('approved','confirmed')",
)


def _ensure_columns() -> None:
    """Fehlende Spalten idempotent ergänzen, obsolete entfernen und Altdaten
    normalisieren, falls eine Migration nicht lief. create_all() ändert
    bestehende Tabellen NICHT."""
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
            for table, col in _DROP_COLUMN_SAFETY_NET:
                if table in tables:
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {col}"))
            if "purchase_orders" in tables:
                for stmt in _DATA_FIXES:
                    conn.execute(text(stmt))
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
app.include_router(storage_locations.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
