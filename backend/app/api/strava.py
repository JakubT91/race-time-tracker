"""Strava OAuth + stažení historie běžce a osobní kalibrace.

Flow:
  1. GET /strava/connect?runner_id=N  -> redirect na Stravu (běžec klikne Authorize)
  2. GET /strava/callback             -> výměna kódu za tokeny, uložení k běžci
  3. POST /strava/runners/{id}/sync   -> stažení aktivit + streams, kalibrace do model_params
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import get_current_user, require_runner
from app.config import settings
from app.db import get_db
from app.services.history.calibrate import calibrate_from_history
from app.services.history.strava import StravaProvider

log = logging.getLogger(__name__)

router = APIRouter(prefix="/strava", tags=["strava"])

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
CALLBACK_URL = f"{settings.backend_base_url.rstrip('/')}/strava/callback"
MAX_ACTIVITIES_WITH_STREAMS = 30  # rate limit Stravy: 100 požadavků / 15 min
HISTORY_MONTHS = 24  # jak stará data ještě vypovídají o aktuální formě


def _require_config():
    if not settings.strava_client_id or not settings.strava_client_secret:
        raise HTTPException(503, "STRAVA_CLIENT_ID/SECRET nejsou nastavené v .env")


def _make_state(runner_id: int) -> str:
    """Podepsaný state, ať nejde do OAuth podstrčit cizí runner_id."""
    exp = int(time.time()) + 600
    return jwt.encode({"rid": runner_id, "exp": exp}, settings.secret_key, algorithm="HS256")


def _read_state(state: str) -> int | None:
    try:
        return int(jwt.decode(state, settings.secret_key, algorithms=["HS256"])["rid"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


@router.get("/connect")
def connect(
    runner_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Vrátí autorizační URL Stravy (frontend na ni přesměruje). Vyžaduje přístup k běžci."""
    _require_config()
    require_runner(runner_id, user, db)
    params = (
        f"client_id={settings.strava_client_id}&response_type=code"
        f"&redirect_uri={CALLBACK_URL}&approval_prompt=auto"
        f"&scope=read,activity:read_all&state={_make_state(runner_id)}"
    )
    return {"authorize_url": f"{AUTHORIZE_URL}?{params}"}


@router.get("/callback")
async def callback(state: str, code: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    # Bez auth hlavičky — sem přesměrovává Strava. Identita běžce je v podepsaném state.
    _require_config()
    if error or code is None:
        return RedirectResponse(f"{settings.public_app_url}?strava=denied")
    runner_id = _read_state(state)
    runner = db.get(models.Runner, runner_id) if runner_id else None
    if runner is None:
        return RedirectResponse(f"{settings.public_app_url}?strava=error")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "authorization_code",
                "code": code,
            },
        )
    if resp.status_code != 200:
        log.error("Strava token exchange selhal: %s", resp.text)
        return RedirectResponse(f"{settings.public_app_url}?strava=error")

    tokens = resp.json()
    runner.strava_access_token = tokens["access_token"]
    runner.strava_refresh_token = tokens["refresh_token"]
    runner.strava_expires_at = tokens["expires_at"]
    db.commit()
    return RedirectResponse(f"{settings.public_app_url}?strava=connected")


async def _fresh_access_token(runner: models.Runner, db: Session) -> str:
    if not runner.strava_access_token:
        raise HTTPException(409, "Běžec nemá propojenou Stravu — nejdřív /strava/connect")
    if runner.strava_expires_at and runner.strava_expires_at > time.time() + 300:
        return runner.strava_access_token

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": runner.strava_refresh_token,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Obnova Strava tokenu selhala: {resp.text}")
    tokens = resp.json()
    runner.strava_access_token = tokens["access_token"]
    runner.strava_refresh_token = tokens["refresh_token"]
    runner.strava_expires_at = tokens["expires_at"]
    db.commit()
    return runner.strava_access_token


@router.post("/runners/{runner_id}/sync")
async def sync_history(
    runner_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Stáhne poslední běhy, spočítá osobní kalibraci a uloží ji do model_params."""
    _require_config()
    runner = require_runner(runner_id, user, db)
    token = await _fresh_access_token(runner, db)
    provider = StravaProvider(token)

    after = datetime.now(timezone.utc) - timedelta(days=HISTORY_MONTHS * 30)
    summaries = await provider.list_activities(after=after)
    if not summaries:
        raise HTTPException(404, f"Na Stravě nejsou žádné běžecké aktivity za posledních {HISTORY_MONTHS} měsíců")

    # Nejdelší běhy vypovídají nejvíc (únava, kopce) — bereme je přednostně
    summaries.sort(key=lambda a: a.distance_m, reverse=True)
    streams = []
    used_ids: set[str] = set()
    for summary in summaries[:MAX_ACTIVITIES_WITH_STREAMS]:
        try:
            s = await provider.get_streams(summary.id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                log.warning("Strava rate limit — kalibruji z %d aktivit", len(streams))
                break
            raise
        if s is not None:
            streams.append(s)
            used_ids.add(summary.id)

    if not streams:
        raise HTTPException(502, "Nepodařilo se stáhnout streams žádné aktivity")

    calibration = calibrate_from_history(streams)
    runner.model_params = {**(runner.model_params or {}), **calibration}

    # Uložíme seznam stažených běhů, ať je dohledatelné, z čeho kalibrace vychází
    db.query(models.SyncedActivity).filter(models.SyncedActivity.runner_id == runner.id).delete()
    for summary in summaries:
        db.add(
            models.SyncedActivity(
                runner_id=runner.id,
                strava_id=summary.id,
                name=summary.name,
                start_date=summary.start,
                distance_m=summary.distance_m,
                moving_time_s=summary.moving_time_s,
                elevation_gain_m=summary.elevation_gain_m,
                avg_heart_rate=summary.avg_heart_rate,
                used_for_calibration=int(summary.id in used_ids),
            )
        )
    db.commit()

    return {
        "runner_id": runner.id,
        "activities_total": len(summaries),
        "activities_used": len(streams),
        "calibration": calibration,
    }


@router.get("/runners/{runner_id}/activities")
def synced_activities(
    runner_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Běhy stažené při posledním syncu (used_for_calibration=1 = šly do kalibrace)."""
    require_runner(runner_id, user, db)
    rows = (
        db.query(models.SyncedActivity)
        .filter(models.SyncedActivity.runner_id == runner_id)
        .order_by(models.SyncedActivity.distance_m.desc())
        .all()
    )
    return [
        {
            "strava_id": r.strava_id,
            "name": r.name,
            "start_date": r.start_date.isoformat(),
            "distance_m": r.distance_m,
            "moving_time_s": r.moving_time_s,
            "elevation_gain_m": r.elevation_gain_m,
            "used_for_calibration": bool(r.used_for_calibration),
        }
        for r in rows
    ]
