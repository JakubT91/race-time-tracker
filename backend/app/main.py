from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — registrace tabulek
from app.api import admin, auth, members, races, runners, strava, ws
from app.config import settings
from app.db import engine
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.migrations import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations(engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Race time tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(races.router)
app.include_router(members.router)
app.include_router(runners.router)
app.include_router(strava.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"status": "ok"}
