"""Rozhraní pro zdroje historie běžce (Strava primárně, Garmin Connect záloha).

Z historie se počítá osobní kalibrace modelu:
  - osobní GAP křivka (tempo vs. sklon z velocity_smooth × grade_smooth streams)
  - osobní únavový koeficient (pokles GAP tempa s km na dlouhých bězích)
  - prahový tep pro interpretaci živého HR
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ActivitySummary:
    id: str
    name: str
    start: datetime
    distance_m: float
    moving_time_s: float
    elevation_gain_m: float
    avg_heart_rate: float | None


@dataclass
class ActivityStreams:
    """Vzorek po vzorku — pole stejné délky."""
    time_s: list[float]
    distance_m: list[float]
    velocity_m_s: list[float]
    grade_pct: list[float] | None
    heart_rate: list[float] | None
    cadence: list[float] | None


class HistoryProvider(ABC):
    @abstractmethod
    async def list_activities(self, after: datetime | None = None) -> list[ActivitySummary]: ...

    @abstractmethod
    async def get_streams(self, activity_id: str) -> ActivityStreams | None: ...
