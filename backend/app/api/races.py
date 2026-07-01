from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth.deps import accessible_race_ids, get_current_user, require_owned_race, require_race
from app.config import settings
from app.db import get_db
from app.services.route_service import build_segments, downsample_profile

router = APIRouter(prefix="/races", tags=["races"])


@router.post("", response_model=schemas.RaceOut)
def create_race(
    payload: schemas.RaceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = models.Race(name=payload.name, start_time=payload.start_time, owner_id=user.id)
    db.add(race)
    db.commit()
    return race


@router.get("", response_model=list[schemas.RaceOut])
def list_races(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ids = accessible_race_ids(user, db)
    if not ids:
        return []
    return (
        db.query(models.Race)
        .filter(models.Race.id.in_(ids))
        .order_by(models.Race.created_at.desc())
        .all()
    )


@router.patch("/{race_id}", response_model=schemas.RaceOut)
def update_race(
    race_id: int,
    payload: schemas.RaceUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_race(race_id, user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(race, key, value)
    db.commit()
    return race


@router.delete("/{race_id}", status_code=204)
def delete_race(
    race_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_owned_race(race_id, user, db)
    db.delete(race)
    db.commit()


@router.post("/{race_id}/gpx", response_model=schemas.RaceOut)
async def upload_gpx(
    race_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_race(race_id, user, db)
    content = (await file.read()).decode("utf-8", errors="replace")
    try:
        segments, total, ascent = build_segments(content, settings.segment_length_m)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    race.gpx_raw = content
    race.segments = [s.to_dict() for s in segments]
    race.total_distance_m = total
    race.total_ascent_m = ascent
    db.commit()
    return race


@router.get("/{race_id}/profile", response_model=schemas.RaceProfile)
def get_profile(race_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    race = require_race(race_id, user, db)
    if not race.segments:
        raise HTTPException(409, "Závod nemá nahranou GPX trasu")
    return schemas.RaceProfile(
        race_id=race.id,
        total_distance_m=race.total_distance_m or 0,
        total_ascent_m=race.total_ascent_m or 0,
        points=[schemas.ProfilePoint(**p) for p in downsample_profile(race.segments)],
    )


@router.post("/{race_id}/aid-stations", response_model=list[schemas.AidStationOut])
def set_aid_stations(
    race_id: int,
    stations: list[schemas.AidStationCreate],
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_race(race_id, user, db)
    race.aid_stations.clear()
    for s in stations:
        race.aid_stations.append(models.AidStation(**s.model_dump()))
    db.commit()
    return race.aid_stations


@router.get("/{race_id}/aid-stations", response_model=list[schemas.AidStationOut])
def list_aid_stations(race_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return require_race(race_id, user, db).aid_stations


@router.post("/{race_id}/runners", response_model=schemas.RunnerOut)
def create_runner(
    race_id: int,
    payload: schemas.RunnerCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_race(race_id, user, db)
    runner = models.Runner(race_id=race.id, **payload.model_dump())
    db.add(runner)
    db.commit()
    return runner


@router.get("/{race_id}/runners", response_model=list[schemas.RunnerOut])
def list_runners(race_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return require_race(race_id, user, db).runners
