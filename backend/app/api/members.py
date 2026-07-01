"""Sdílení závodu — vlastník zve další uživatele (support tým)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import get_current_user, require_owned_race, require_race
from app.db import get_db

router = APIRouter(prefix="/races", tags=["sharing"])


class InviteRequest(BaseModel):
    email: str


class MemberOut(BaseModel):
    user_id: int
    email: str
    role: str


def _normalize(email: str) -> str:
    return email.strip().lower()


@router.get("/{race_id}/members", response_model=list[MemberOut])
def list_members(race_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    race = require_race(race_id, user, db)
    out: list[MemberOut] = []
    if race.owner_id:
        owner = db.get(models.User, race.owner_id)
        if owner:
            out.append(MemberOut(user_id=owner.id, email=owner.email, role="owner"))
    members = db.query(models.RaceMember).filter(models.RaceMember.race_id == race.id).all()
    for m in members:
        u = db.get(models.User, m.user_id)
        if u and u.id != race.owner_id:
            out.append(MemberOut(user_id=u.id, email=u.email, role="member"))
    return out


@router.post("/{race_id}/members", response_model=MemberOut)
def invite_member(
    race_id: int,
    payload: InviteRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_owned_race(race_id, user, db)
    email = _normalize(payload.email)
    if "@" not in email:
        raise HTTPException(422, "Zadej platný e-mail")

    invitee = db.query(models.User).filter(models.User.email == email).first()
    if invitee is None:
        invitee = models.User(email=email)
        db.add(invitee)
        db.commit()

    if invitee.id == race.owner_id:
        raise HTTPException(409, "Tento uživatel je vlastník závodu")

    existing = (
        db.query(models.RaceMember)
        .filter(models.RaceMember.race_id == race.id, models.RaceMember.user_id == invitee.id)
        .first()
    )
    if existing is None:
        db.add(models.RaceMember(race_id=race.id, user_id=invitee.id))
        db.commit()

    # Pozvaný se přihlásí běžně přes magic link (na svůj e-mail) a závod uvidí.
    return MemberOut(user_id=invitee.id, email=invitee.email, role="member")


@router.delete("/{race_id}/members/{user_id}", status_code=204)
def remove_member(
    race_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    race = require_owned_race(race_id, user, db)
    if user_id == race.owner_id:
        raise HTTPException(409, "Vlastníka nelze odebrat")
    member = (
        db.query(models.RaceMember)
        .filter(models.RaceMember.race_id == race.id, models.RaceMember.user_id == user_id)
        .first()
    )
    if member:
        db.delete(member)
        db.commit()
