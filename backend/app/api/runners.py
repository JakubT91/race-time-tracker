from datetime import timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.deps import get_current_user, require_runner
from app.config import settings
from app.db import get_db
from app.services.prediction.engine import (
    build_params_for_runner,
    deterministic_seconds_per_segment,
    simulate,
)
from app.services.weather import factors_for_segments, fetch_hourly_forecast

router = APIRouter(prefix="/runners", tags=["runners"])


async def run_prediction(runner: models.Runner, db: Session) -> models.PredictionRun:
    """Sestaví parametry (kalibrace, počasí, tma, rekalibrační overrides) a spustí simulaci."""
    race = runner.race
    if not race.segments:
        raise HTTPException(409, "Závod nemá nahranou GPX trasu")

    aid_stations = [
        {"name": a.name, "distance_m": a.distance_m, "expected_stop_s": a.expected_stop_s}
        for a in race.aid_stations
    ]
    overrides = runner.model_params or {}

    params = build_params_for_runner(
        segments=race.segments,
        target_time_s=runner.target_time_s,
        feel=runner.feel,
        aid_stations=aid_stations,
        race_start=race.start_time,
        overrides=overrides,
        n_runs=settings.monte_carlo_runs,
    )

    # Počasí: předpověď pro střed trasy, faktor podle hodiny průchodu
    if race.start_time is not None:
        mid = race.segments[len(race.segments) // 2]
        hourly = await fetch_hourly_forecast(mid["lat"], mid["lon"])
        if hourly is not None:
            eta = np.cumsum(deterministic_seconds_per_segment(race.segments, params))
            params.weather_factors = factors_for_segments(race.segments, race.start_time, eta, hourly)

    result = simulate(race.segments, params)
    run = models.PredictionRun(
        runner_id=runner.id,
        results={
            "finish": result.finish,
            "per_km": result.per_km,
            "aid_stations": result.aid_stations,
            "params": {
                "base_pace_s_per_km": params.base_pace_s_per_km,
                "base_pace_sigma": params.base_pace_sigma,
                "fatigue_k": params.fatigue_k,
            },
        },
    )
    db.add(run)
    db.commit()
    return run


def _latest_position(runner: models.Runner, db: Session) -> models.Trackpoint | None:
    return (
        db.query(models.Trackpoint)
        .filter(models.Trackpoint.runner_id == runner.id, models.Trackpoint.route_distance_m.isnot(None))
        .order_by(models.Trackpoint.timestamp.desc())
        .first()
    )


def _to_prediction_out(run: models.PredictionRun, position_m: float | None) -> schemas.PredictionOut:
    r = run.results
    created = run.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return schemas.PredictionOut(
        runner_id=run.runner_id,
        created_at=created,
        finish=schemas.Percentiles(**r["finish"]),
        per_km=[schemas.KmPrediction(**p) for p in r["per_km"]],
        aid_stations=[schemas.AidStationPrediction(**a) for a in r["aid_stations"]],
        runner_position_m=position_m,
    )


@router.patch("/{runner_id}", response_model=schemas.RunnerOut)
def update_runner(
    runner_id: int,
    payload: schemas.RunnerUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    runner = require_runner(runner_id, user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(runner, key, value)
    db.commit()
    return runner


@router.post("/{runner_id}/predict", response_model=schemas.PredictionOut)
async def predict(runner_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    runner = require_runner(runner_id, user, db)
    run = await run_prediction(runner, db)
    pos = _latest_position(runner, db)
    return _to_prediction_out(run, pos.route_distance_m if pos else None)


@router.get("/{runner_id}/prediction/latest", response_model=schemas.PredictionOut)
def latest_prediction(runner_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    runner = require_runner(runner_id, user, db)
    run = (
        db.query(models.PredictionRun)
        .filter(models.PredictionRun.runner_id == runner.id)
        .order_by(models.PredictionRun.created_at.desc())
        .first()
    )
    if run is None:
        raise HTTPException(404, "Zatím žádná predikce — zavolej POST /runners/{id}/predict")
    pos = _latest_position(runner, db)
    return _to_prediction_out(run, pos.route_distance_m if pos else None)


@router.get("/{runner_id}/status", response_model=schemas.RunnerStatus)
def runner_status(runner_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    runner = require_runner(runner_id, user, db)
    pos = _latest_position(runner, db)
    return schemas.RunnerStatus(
        runner_id=runner.id,
        route_distance_m=pos.route_distance_m if pos else None,
        last_seen=pos.timestamp if pos else None,
        is_paused=bool(pos.is_paused) if pos else False,
    )
