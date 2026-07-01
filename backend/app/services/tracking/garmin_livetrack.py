"""Garmin LiveTrack poller.

POZOR: nedokumentované API — struktura se mezi verzemi liší, všechna pole
parsujeme defenzivně. Před závodem vždy otestovat se skutečnými hodinkami.

Endpointy (z sdíleného odkazu livetrack.garmin.com/session/{sessionId}/{token}):
  services/session/{sessionId}/token/{token}            ... metadata sezení
  services/trackLog/{sessionId}/token/{token}?from=...  ... trackpointy
Novější sezení vracejí body s vnořeným objektem `fitnessPointData`
(heartRateBeatsPerMin, cadenceCyclesPerMin, powerWatts, speedMetersPerSec...).
"""

import re
from datetime import datetime, timezone

import httpx

from app.services.tracking.base import LivePoint, TrackingProvider

URL_PATTERN = re.compile(r"livetrack\.garmin\.com/session/(?P<session>[\w-]+)/(?P<token>[\w-]+)")
BASE = "https://livetrack.garmin.com/services"


def _parse_timestamp(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # ms epoch
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _get(d: dict, *keys, default=None):
    """Vrátí první existující klíč — názvy polí se mezi verzemi API liší."""
    for key in keys:
        if isinstance(d, dict) and d.get(key) is not None:
            return d[key]
    return default


class GarminLiveTrackProvider(TrackingProvider):
    def matches(self, url: str) -> bool:
        return bool(URL_PATTERN.search(url))

    def _ids(self, url: str) -> tuple[str, str]:
        m = URL_PATTERN.search(url)
        if not m:
            raise ValueError(f"Neplatný LiveTrack odkaz: {url}")
        return m.group("session"), m.group("token")

    async def fetch_points(self, url: str, since: datetime | None = None) -> list[LivePoint]:
        session_id, token = self._ids(url)
        params = {}
        if since is not None:
            params["from"] = int(since.timestamp() * 1000)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE}/trackLog/{session_id}/token/{token}", params=params)
            resp.raise_for_status()
            payload = resp.json()

        raw_points = payload if isinstance(payload, list) else _get(payload, "trackPoints", "trackLog", default=[])
        points: list[LivePoint] = []
        for rp in raw_points:
            position = _get(rp, "position", default=rp)
            lat = _get(position, "lat", "latitude")
            lon = _get(position, "lon", "lng", "longitude")
            ts = _parse_timestamp(_get(rp, "dateTime", "timestamp"))
            if lat is None or lon is None or ts is None:
                continue

            fitness = _get(rp, "fitnessPointData", default={}) or {}
            metadata = _get(rp, "metaData", "metadata", default={}) or {}
            events = _get(rp, "eventTypes", "events", default=[]) or []

            points.append(
                LivePoint(
                    timestamp=ts,
                    lat=float(lat),
                    lon=float(lon),
                    elevation=_get(rp, "altitude", "elevation") or _get(metadata, "ELEVATION"),
                    speed_m_s=_get(fitness, "speedMetersPerSec") or _get(rp, "speed") or _get(metadata, "SPEED"),
                    heart_rate=_get(fitness, "heartRateBeatsPerMin") or _get(rp, "heartRate"),
                    cadence=_get(fitness, "cadenceCyclesPerMin") or _get(rp, "cadence"),
                    power_w=_get(fitness, "powerWatts") or _get(rp, "power"),
                    is_paused="PAUSE" in [str(e).upper() for e in events],
                )
            )
        return points


PROVIDERS: list[TrackingProvider] = [GarminLiveTrackProvider()]


def provider_for(url: str) -> TrackingProvider | None:
    return next((p for p in PROVIDERS if p.matches(url)), None)
