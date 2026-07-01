"""Admin sekce (jen pro administrátory) — přehled uživatelů a závodů."""

import smtplib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import require_admin
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/mail-test")
def mail_test():
    """Diagnostika odesílání e-mailů — jaký transport a jestli SMTP spojení + login projde."""
    out = {
        "smtp_host": settings.smtp_host or "(prázdné)",
        "smtp_port": settings.smtp_port,
        "smtp_user_set": bool(settings.smtp_user),
        "smtp_password_set": bool(settings.smtp_password),
        "resend_set": bool(settings.resend_api_key),
    }
    if settings.smtp_host and settings.smtp_user and settings.smtp_password:
        out["transport"] = "smtp (Gmail)"
        try:
            if settings.smtp_port == 465:
                srv = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
            else:
                srv = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
                srv.starttls()
            srv.login(settings.smtp_user, settings.smtp_password)
            srv.quit()
            out["smtp_ok"] = True
        except Exception as exc:  # noqa: BLE001
            out["smtp_ok"] = False
            out["smtp_error"] = f"{type(exc).__name__}: {exc}"
    elif settings.resend_api_key:
        out["transport"] = "resend"
    else:
        out["transport"] = "žádný (jen log)"
    return out


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
