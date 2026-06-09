from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .models.audit import UserProfile
from .routers import admin, auth, contact, erp, health

settings = get_settings()


def _bootstrap_admin() -> None:
    """Promote a user to admin on startup if no admin exists yet."""
    db = SessionLocal()
    try:
        has_admin = db.query(UserProfile).filter(
            UserProfile.role == "admin", UserProfile.is_active == True
        ).first()
        if has_admin:
            return
        candidate = None
        if settings.initial_admin_email:
            candidate = db.query(UserProfile).filter(
                UserProfile.email == settings.initial_admin_email,
                UserProfile.is_active == True,
            ).first()
        if not candidate:
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
    _bootstrap_admin()
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
