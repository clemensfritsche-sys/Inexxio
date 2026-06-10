from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import inspect, text

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models.audit import UserProfile
from .routers import admin, auth, contact, erp, health

settings = get_settings()


def _apply_schema_fix() -> None:
    """Apply pending schema changes if alembic couldn't run at startup."""
    with engine.connect() as conn:
        cols = {c['name'] for c in inspect(conn).get_columns('user_profiles')}

        # Rename state_canton → state_region
        if 'state_canton' in cols and 'state_region' not in cols:
            conn.execute(text("ALTER TABLE user_profiles RENAME COLUMN state_canton TO state_region"))
            conn.commit()
            cols = {c['name'] for c in inspect(conn).get_columns('user_profiles')}
            print("INFO: Renamed state_canton → state_region", flush=True)
        elif 'state_canton' in cols:
            conn.execute(text("ALTER TABLE user_profiles DROP COLUMN state_canton"))
            conn.commit()
            cols = {c['name'] for c in inspect(conn).get_columns('user_profiles')}

        # Remove legacy columns
        for col in [
            'display_name', 'salutation', 'phone_mobile',
            'ship_b2c_first_name', 'ship_b2c_last_name', 'ship_b2c_address_line1',
            'ship_b2c_address_line2', 'ship_b2c_city', 'ship_b2c_postal_code', 'ship_b2c_country',
            'ship_b2b_company', 'ship_b2b_contact', 'ship_b2b_address_line1',
            'ship_b2b_address_line2', 'ship_b2b_city', 'ship_b2b_postal_code', 'ship_b2b_country',
            'invoice_vat_id', 'company_legal_form', 'timezone',
            'is_business', 'customer_group', 'credit_limit', 'accepts_marketing', 'stripe_customer_id',
        ]:
            if col in cols:
                conn.execute(text(f"ALTER TABLE user_profiles DROP COLUMN {col}"))
                conn.commit()

        cols = {c['name'] for c in inspect(conn).get_columns('user_profiles')}

        # Add missing columns
        new_cols = {
            'state_region': 'VARCHAR(100)',
            'ship_name': 'VARCHAR(255)', 'ship_company': 'VARCHAR(255)',
            'ship_address_line1': 'VARCHAR(255)', 'ship_address_line2': 'VARCHAR(255)',
            'ship_city': 'VARCHAR(100)', 'ship_postal_code': 'VARCHAR(20)',
            'ship_state_region': 'VARCHAR(100)', 'ship_country': 'VARCHAR(100)',
            'bank_account_holder': 'VARCHAR(255)', 'bank_iban': 'VARCHAR(50)',
            'bank_bic': 'VARCHAR(20)', 'bank_name': 'VARCHAR(255)',
        }
        for col_name, col_type in new_cols.items():
            if col_name not in cols:
                conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"INFO: Added column {col_name}", flush=True)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        Base.metadata.create_all(bind=engine)
    try:
        _apply_schema_fix()
    except Exception as e:
        print(f"WARNING: _apply_schema_fix() failed: {e}", flush=True)
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


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
