"""Magic-link přihlášení: požádat o odkaz -> ověřit -> session token."""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth.deps import get_current_user
from app.auth.email import send_magic_link
from app.auth.security import create_session_token, generate_magic_token, hash_token
from app.config import settings
from app.db import get_db
from app.models import utcnow

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str


class AuthVerify(BaseModel):
    token: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    is_admin: bool = False


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


def _user_out(user: models.User) -> "UserOut":
    return UserOut(id=user.id, email=user.email, name=user.name, is_admin=settings.is_admin(user.email))


def _normalize(email: str) -> str:
    return email.strip().lower()


@router.post("/request")
async def request_link(payload: AuthRequest, db: Session = Depends(get_db)):
    email = _normalize(payload.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Zadej platný e-mail")
    if not settings.is_email_allowed(email):
        raise HTTPException(403, "Tento e-mail nemá přístup do aplikace. Požádej správce o přidání.")
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(email=email)
        db.add(user)
        db.commit()

    raw, token_hash = generate_magic_token()
    db.add(
        models.MagicLinkToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(minutes=settings.magic_link_ttl_min),
        )
    )
    db.commit()

    link = f"{settings.public_app_url.rstrip('/')}/auth/verify?token={raw}"
    try:
        await send_magic_link(email, link)
    except Exception:
        # Selhání e-mailu nesmí shodit přihlášení (token je uložen; uživatel zkusí znovu)
        log.exception("Odeslání přihlašovacího odkazu selhalo pro %s", email)

    # Jen v lokálním vývoji (dev_mode) a bez e-mailové služby vrátíme odkaz rovnou.
    # V produkci se NIKDY nevrací — jinak by šlo přihlásit se za cizí e-mail.
    out: dict = {"sent": True}
    if settings.dev_mode and not settings.resend_api_key:
        out["dev_magic_link"] = link
    return out


@router.post("/verify", response_model=TokenOut)
def verify(payload: AuthVerify, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.token.strip())
    row = (
        db.query(models.MagicLinkToken)
        .filter(models.MagicLinkToken.token_hash == token_hash)
        .first()
    )
    now = utcnow()
    expires = row.expires_at if row else None
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=now.tzinfo)
    if row is None or row.used_at is not None or expires < now:
        raise HTTPException(400, "Odkaz je neplatný nebo expirovaný — vyžádej si nový")

    row.used_at = now
    user = db.get(models.User, row.user_id)
    user.last_login_at = now
    db.commit()

    return TokenOut(access_token=create_session_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return _user_out(user)
