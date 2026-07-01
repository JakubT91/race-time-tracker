"""Admin sekce (jen pro administrátory) — přehled uživatelů a závodů."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import require_admin
from app.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {
        "users": db.query(models.User).count(),
        "races": db.query(models.Race).count(),
        "runners": db.query(models.Runner).count(),
        "predictions": db.query(models.PredictionRun).count(),
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    owned = dict(
        db.query(models.Race.owner_id, func.count(models.Race.id))
        .group_by(models.Race.owner_id)
        .all()
    )
    memberships = dict(
        db.query(models.RaceMember.user_id, func.count(models.RaceMember.id))
        .group_by(models.RaceMember.user_id)
        .all()
    )
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "created_at": _iso(u.created_at),
            "last_login_at": _iso(u.last_login_at),
            "races_owned": owned.get(u.id, 0),
            "memberships": memberships.get(u.id, 0),
        }
        for u in users
    ]


@router.get("/races")
def list_races(db: Session = Depends(get_db)):
    runner_counts = dict(
        db.query(models.Runner.race_id, func.count(models.Runner.id)).group_by(models.Runner.race_id).all()
    )
    aid_counts = dict(
        db.query(models.AidStation.race_id, func.count(models.AidStation.id)).group_by(models.AidStation.race_id).all()
    )
    owners = {u.id: u.email for u in db.query(models.User).all()}
    races = db.query(models.Race).order_by(models.Race.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "owner_email": owners.get(r.owner_id) if r.owner_id else None,
            "start_time": _iso(r.start_time),
            "total_distance_m": r.total_distance_m,
            "total_ascent_m": r.total_ascent_m,
            "runners": runner_counts.get(r.id, 0),
            "aid_stations": aid_counts.get(r.id, 0),
            "created_at": _iso(r.created_at),
        }
        for r in races
    ]
