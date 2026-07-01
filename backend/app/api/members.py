"""Sdílení závodu — vlastník zve další uživatele (support tým)."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import get_current_user, require_owned_race, require_race
from app.auth.email import send_invite
from app.auth.security import generate_magic_token
from app.config import settings
from app.db import get_db
from app.models import utcnow

log = logging.getLogger(__name__)

router = APIRouter(prefix="/races", tags=["sharing"])

# Pozvánkový přihlašovací odkaz platí déle než běžný (pozvaný nemusí kliknout hned)
INVITE_LINK_TTL_DAYS = 30


def _runner_label(race: models.Race) -> str:
    names = [r.name for r in race.runners]
    if not names:
        return "tohoto závodu"
    if len(names) == 1:
        return f"běžce {names[0]}"
    return "běžců " + ", ".join(names)


class InviteRequest(BaseModel):
    email: str


class MemberOut(BaseModel):
    user_id: int
    email: str
    role: str
    # Přihlašovací odkaz — vrací se jen při pozvání, ať ho vlastník může poslat
    # kamarádovi (např. přes WhatsApp), když nechodí e-maily.
    login_link: str | None = None


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
async def invite_member(
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
        db.commit()  # členství = pozvaný má přístup a smí se přihlásit (viz email_has_access)

    # Přihlašovací odkaz přímo do e-mailu pozvánky, ať stačí kliknout
    raw, token_hash = generate_magic_token()
    db.add(
        models.MagicLinkToken(
            user_id=invitee.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(days=INVITE_LINK_TTL_DAYS),
        )
    )
    db.commit()
    link = f"{settings.public_app_url.rstrip('/')}/auth/verify?token={raw}"
    try:
        await send_invite(invitee.email, link, race.name, _runner_label(race))
    except Exception:
        log.exception("Odeslání pozvánky selhalo pro %s", invitee.email)

    # Odkaz vracíme i vlastníkovi, ať ho může poslat sám (nezávisle na e-mailu)
    return MemberOut(user_id=invitee.id, email=invitee.email, role="member", login_link=link)


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
