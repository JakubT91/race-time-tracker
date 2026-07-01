"""Rozhraní pro poskytovatele live trackingu — Garmin LiveTrack teď, inReach/Strava Beacon později."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LivePoint:
    timestamp: datetime
    lat: float
    lon: float
    elevation: float | None = None
    speed_m_s: float | None = None
    heart_rate: float | None = None
    cadence: float | None = None
    power_w: float | None = None
    is_paused: bool = False


class TrackingProvider(ABC):
    @abstractmethod
    def matches(self, url: str) -> bool:
        """Umí tento provider daný sdílený odkaz?"""

    @abstractmethod
    async def fetch_points(self, url: str, since: datetime | None = None) -> list[LivePoint]:
        """Stáhne nové trackpointy (inkrementálně od `since`)."""
