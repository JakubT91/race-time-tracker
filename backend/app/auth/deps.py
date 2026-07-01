"""Závislosti pro autentizaci a kontrolu přístupu."""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.auth.security import decode_session_token
from app.config import settings
from app.db import get_db


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Chybí přihlášení")
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_session_token(token)
    if user_id is None:
        raise HTTPException(401, "Neplatné nebo expirované přihlášení")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(401, "Uživatel neexistuje")
    if not settings.is_email_allowed(user.email):
        raise HTTPException(403, "Tvůj přístup byl odebrán.")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not settings.is_admin(user.email):
        raise HTTPException(403, "Přístup jen pro administrátora")
    return user


def user_has_race_access(race: models.Race, user: models.User, db: Session) -> bool:
    if race.owner_id == user.id:
        return True
    member = (
        db.query(models.RaceMember)
        .filter(models.RaceMember.race_id == race.id, models.RaceMember.user_id == user.id)
        .first()
    )
    return member is not None


def require_race(race_id: int, user: models.User, db: Session) -> models.Race:
    race = db.get(models.Race, race_id)
    if race is None:
        raise HTTPException(404, "Závod nenalezen")
    if not user_has_race_access(race, user, db):
        raise HTTPException(403, "K tomuto závodu nemáš přístup")
    return race


def require_owned_race(race_id: int, user: models.User, db: Session) -> models.Race:
    """Akce vyhrazené vlastníkovi (sdílení, smazání)."""
    race = db.get(models.Race, race_id)
    if race is None:
        raise HTTPException(404, "Závod nenalezen")
    if race.owner_id != user.id:
        raise HTTPException(403, "Tuto akci může provést jen vlastník závodu")
    return race


def require_runner(runner_id: int, user: models.User, db: Session) -> models.Runner:
    runner = db.get(models.Runner, runner_id)
    if runner is None:
        raise HTTPException(404, "Běžec nenalezen")
    race = db.get(models.Race, runner.race_id)
    if race is None or not user_has_race_access(race, user, db):
        raise HTTPException(403, "K tomuto běžci nemáš přístup")
    return runner


def accessible_race_ids(user: models.User, db: Session) -> list[int]:
    """ID závodů, které uživatel vlastní nebo je jejich členem."""
    owned = db.query(models.Race.id).filter(models.Race.owner_id == user.id)
    member = (
        db.query(models.Race.id)
        .join(models.RaceMember, models.RaceMember.race_id == models.Race.id)
        .filter(models.RaceMember.user_id == user.id)
    )
    return [r[0] for r in owned.union(member).all()]
