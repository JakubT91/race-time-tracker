from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RaceMember(Base):
    """Sdílení závodu: vlastník může pozvat další uživatele (support tým)."""

    __tablename__ = "race_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")  # member | owner
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Vlastník závodu (může chybět u dat z doby před zavedením účtů)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)

    # Výstup segmentace GPX: [{start_m, end_m, grade, ele, lat, lon}, ...]
    segments: Mapped[list | None] = mapped_column(JSON)
    total_distance_m: Mapped[float | None] = mapped_column(Float)
    total_ascent_m: Mapped[float | None] = mapped_column(Float)
    gpx_raw: Mapped[str | None] = mapped_column(Text)

    aid_stations: Mapped[list["AidStation"]] = relationship(back_populates="race", cascade="all, delete-orphan")
    runners: Mapped[list["Runner"]] = relationship(back_populates="race", cascade="all, delete-orphan")
    members: Mapped[list["RaceMember"]] = relationship(cascade="all, delete-orphan")


class AidStation(Base):
    __tablename__ = "aid_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    name: Mapped[str] = mapped_column(String(100))
    distance_m: Mapped[float] = mapped_column(Float)
    expected_stop_s: Mapped[float] = mapped_column(Float, default=180.0)

    race: Mapped[Race] = relationship(back_populates="aid_stations")


class Runner(Base):
    __tablename__ = "runners"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"))
    name: Mapped[str] = mapped_column(String(200))
    target_time_s: Mapped[float] = mapped_column(Float)
    # Subjektivní pocit 1 (skvělý) .. 5 (špatný)
    feel: Mapped[int] = mapped_column(Integer, default=3)
    livetrack_url: Mapped[str | None] = mapped_column(String(500))

    # Kalibrované parametry modelu (aktualizované za závodu i z historie)
    # {base_pace_s_per_km, base_pace_sigma, fatigue_k, fatigue_p, gap_uphill_scale, ...}
    model_params: Mapped[dict | None] = mapped_column(JSON)

    # Strava OAuth tokeny (propojení historie)
    strava_access_token: Mapped[str | None] = mapped_column(String(100))
    strava_refresh_token: Mapped[str | None] = mapped_column(String(100))
    strava_expires_at: Mapped[int | None] = mapped_column(Integer)

    race: Mapped[Race] = relationship(back_populates="runners")
    trackpoints: Mapped[list["Trackpoint"]] = relationship(back_populates="runner", cascade="all, delete-orphan")
    predictions: Mapped[list["PredictionRun"]] = relationship(back_populates="runner", cascade="all, delete-orphan")


class Trackpoint(Base):
    __tablename__ = "trackpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runners.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    elevation: Mapped[float | None] = mapped_column(Float)
    speed_m_s: Mapped[float | None] = mapped_column(Float)
    # Poloha namapovaná na staničení trasy
    route_distance_m: Mapped[float | None] = mapped_column(Float)
    # Senzory z LiveTracku — frontend je nezobrazuje, model je využívá (kardiální drift, únava)
    heart_rate: Mapped[float | None] = mapped_column(Float)
    cadence: Mapped[float | None] = mapped_column(Float)
    power_w: Mapped[float | None] = mapped_column(Float)
    is_paused: Mapped[int] = mapped_column(Integer, default=0)

    runner: Mapped[Runner] = relationship(back_populates="trackpoints")


class SyncedActivity(Base):
    """Běhy stažené ze Stravy pro kalibraci — ať je vidět, z čeho model vychází."""

    __tablename__ = "synced_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runners.id"))
    strava_id: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(300), default="")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    distance_m: Mapped[float] = mapped_column(Float)
    moving_time_s: Mapped[float] = mapped_column(Float)
    elevation_gain_m: Mapped[float] = mapped_column(Float)
    avg_heart_rate: Mapped[float | None] = mapped_column(Float)
    # 1 = stáhly se detailní streams a běh šel do kalibrace
    used_for_calibration: Mapped[int] = mapped_column(Integer, default=0)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runners.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # {finish: {p10,p50,p90}, per_km: [{km, p10,p50,p90}], aid_stations: [...], params: {...}}
    results: Mapped[dict] = mapped_column(JSON)

    runner: Mapped[Runner] = relationship(back_populates="predictions")
