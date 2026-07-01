"""Polling Garmin LiveTrack -> uložení trackpointů -> rekalibrace -> nová predikce -> WS push."""

import logging
from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import models
from app.api.runners import run_prediction
from app.api.ws import manager
from app.config import settings
from app.db import SessionLocal
from app.services.calibration import recalibrate
from app.services.tracking.garmin_livetrack import provider_for
from app.services.tracking.matcher import match_to_route

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def poll_all_runners():
    db = SessionLocal()
    try:
        runners = (
            db.query(models.Runner)
            .filter(models.Runner.livetrack_url.isnot(None))
            .all()
        )
        for runner in runners:
            try:
                await _poll_runner(runner, db)
            except Exception:
                log.exception("Polling běžce %s selhal", runner.id)
    finally:
        db.close()


async def _poll_runner(runner: models.Runner, db):
    provider = provider_for(runner.livetrack_url)
    if provider is None:
        return

    last = (
        db.query(models.Trackpoint)
        .filter(models.Trackpoint.runner_id == runner.id)
        .order_by(models.Trackpoint.timestamp.desc())
        .first()
    )
    since = last.timestamp.replace(tzinfo=timezone.utc) if last and last.timestamp.tzinfo is None else (last.timestamp if last else None)

    points = await provider.fetch_points(runner.livetrack_url, since=since)
    if not points:
        return

    last_dist = last.route_distance_m if last else None
    for p in sorted(points, key=lambda x: x.timestamp):
        route_dist = None
        if runner.race.segments:
            route_dist = match_to_route(runner.race.segments, p.lat, p.lon, last_distance_m=last_dist)
            if route_dist is not None:
                last_dist = route_dist
        db.add(
            models.Trackpoint(
                runner_id=runner.id,
                timestamp=p.timestamp,
                lat=p.lat,
                lon=p.lon,
                elevation=p.elevation,
                speed_m_s=p.speed_m_s,
                route_distance_m=route_dist,
                heart_rate=p.heart_rate,
                cadence=p.cadence,
                power_w=p.power_w,
                is_paused=int(p.is_paused),
            )
        )
    db.commit()

    # Rekalibrace z dosavadního průběhu
    if runner.race.segments:
        track = [
            {
                "route_distance_m": t.route_distance_m,
                "timestamp_s": t.timestamp.timestamp(),
                "is_paused": bool(t.is_paused),
            }
            for t in runner.trackpoints
        ]
        prior = (runner.model_params or {}).get("base_pace_s_per_km")
        if prior is None:
            latest_run = (
                db.query(models.PredictionRun)
                .filter(models.PredictionRun.runner_id == runner.id)
                .order_by(models.PredictionRun.created_at.desc())
                .first()
            )
            prior = (latest_run.results.get("params", {}).get("base_pace_s_per_km") if latest_run else None)
        if prior:
            overrides = recalibrate(runner.race.segments, track, prior_base_pace=prior)
            if overrides:
                runner.model_params = {**(runner.model_params or {}), **overrides}
                db.commit()

    run = await run_prediction(runner, db)
    await manager.broadcast(
        runner.id,
        {
            "type": "prediction_update",
            "runner_id": runner.id,
            "position_m": last_dist,
            "finish": run.results["finish"],
        },
    )


def start_scheduler():
    scheduler.add_job(poll_all_runners, "interval", seconds=settings.livetrack_poll_seconds, max_instances=1)
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
