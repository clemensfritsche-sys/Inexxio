from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.auth import init_firebase
from app.routers import health, items, auth as auth_router, contact


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    yield


app = FastAPI(
    title="Inexxio API",
    version="0.1.0",
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url="/api/redoc" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "INTERNAL_ERROR"},
    )


app.include_router(health.router)
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
app.include_router(contact.router, prefix="/api/v1")
