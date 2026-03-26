"""Fakturovatko API + static frontend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import Base, engine, migrate_schema
from app.routers import api_orders, api_public, health, internal

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(api_public.router)
app.include_router(api_orders.router)
app.include_router(internal.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    migrate_schema()


static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
