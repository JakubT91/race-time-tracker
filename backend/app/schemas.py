from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RaceCreate(BaseModel):
    name: str
    start_time: datetime | None = None


class RaceUpdate(BaseModel):
    name: str | None = None
    start_time: datetime | None = None


class RaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_time: datetime | None
    total_distance_m: float | None
    total_ascent_m: float | None
    owner_id: int | None = None


class ProfilePoint(BaseModel):
    km: float
    ele: float


class RaceProfile(BaseModel):
    race_id: int
    total_distance_m: float
    total_ascent_m: float
    points: list[ProfilePoint]


class AidStationCreate(BaseModel):
    name: str
    distance_m: float
    expected_stop_s: float = 180.0


class AidStationOut(AidStationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RunnerCreate(BaseModel):
    name: str
    target_time_s: float = Field(gt=0)
    feel: int = Field(default=3, ge=1, le=5)
    livetrack_url: str | None = None


class RunnerUpdate(BaseModel):
    name: str | None = None
    target_time_s: float | None = Field(default=None, gt=0)
    feel: int | None = Field(default=None, ge=1, le=5)
    livetrack_url: str | None = None


class RunnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    race_id: int
    name: str
    target_time_s: float
    feel: int
    livetrack_url: str | None


class Percentiles(BaseModel):
    p10: float
    p50: float
    p90: float


class KmPrediction(Percentiles):
    km: float


class AidStationPrediction(Percentiles):
    name: str
    distance_m: float


class PredictionOut(BaseModel):
    runner_id: int
    created_at: datetime
    finish: Percentiles
    per_km: list[KmPrediction]
    aid_stations: list[AidStationPrediction]
    runner_position_m: float | None = None


class RunnerStatus(BaseModel):
    runner_id: int
    route_distance_m: float | None
    last_seen: datetime | None
    is_paused: bool = False
