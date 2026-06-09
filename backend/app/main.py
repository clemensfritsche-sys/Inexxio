from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .core.config import get_settings
from .core.database import Base, engine
from .routers import admin, auth, auftraege, boms, companies, health, items, objekte, objekttypen, objects, uni_objekte, work_plans

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        Base.metadata.create_all(bind=engine)
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
app.include_router(objects.router)
app.include_router(items.router)
app.include_router(boms.router)
app.include_router(work_plans.router)
app.include_router(auftraege.router)
app.include_router(objekte.router)
app.include_router(uni_objekte.router)
app.include_router(companies.router)
app.include_router(admin.router)
app.include_router(objekttypen.router)


@app.get("/")
async def root():
    return {
        "name": "Inexxio ECS API",
        "version": settings.app_version,
        "docs": "/api/docs",
    }
