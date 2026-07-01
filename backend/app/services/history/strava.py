"""Strava API klient — historie běžce pro osobní kalibraci modelu.

Setup:
  1. Vytvořit aplikaci na https://www.strava.com/settings/api
  2. STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET do .env
  3. OAuth flow se scope activity:read_all; access token expiruje po 6 h -> refresh token

Rate limity: 100 požadavků / 15 min, 1000 / den na sportovce.
"""

from datetime import datetime

import httpx

from app.config import settings
from app.services.history.base import ActivityStreams, ActivitySummary, HistoryProvider

API = "https://www.strava.com/api/v3"
STREAM_KEYS = "time,distance,velocity_smooth,grade_smooth,heartrate,cadence"

# Jen běh a trail — kolo/chůze/VirtualRun (pás, Zwift) by kalibraci zkreslily
ALLOWED_SPORT_TYPES = {"Run", "TrailRun"}


def _is_run(activity: dict) -> bool:
    # `sport_type` je novější a rozlišuje TrailRun; starší `type` hlásí trail jen jako Run
    sport = activity.get("sport_type") or activity.get("type")
    return sport in ALLOWED_SPORT_TYPES


class StravaProvider(HistoryProvider):
    def __init__(self, access_token: str):
        self.access_token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def list_activities(self, after: datetime | None = None) -> list[ActivitySummary]:
        """Stránkuje přes všechny aktivity od `after` (1 požadavek na 200 aktivit)."""
        results: list[ActivitySummary] = []
        async with httpx.AsyncClient(timeout=20) as client:
            page = 1
            while True:
                params: dict = {"per_page": 200, "page": page}
                if after:
                    params["after"] = int(after.timestamp())
                resp = await client.get(f"{API}/athlete/activities", headers=self._headers(), params=params)
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                results.extend(
                    ActivitySummary(
                        id=str(a["id"]),
                        name=a.get("name", ""),
                        start=datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")),
                        distance_m=a.get("distance", 0.0),
                        moving_time_s=a.get("moving_time", 0.0),
                        elevation_gain_m=a.get("total_elevation_gain", 0.0),
                        avg_heart_rate=a.get("average_heartrate"),
                    )
                    for a in batch
                    if _is_run(a)
                )
                if len(batch) < 200:
                    break
                page += 1
        return results

    async def get_streams(self, activity_id: str) -> ActivityStreams | None:
        params = {"keys": STREAM_KEYS, "key_by_type": "true"}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{API}/activities/{activity_id}/streams", headers=self._headers(), params=params
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        data = resp.json()
        if "time" not in data or "velocity_smooth" not in data:
            return None
        return ActivityStreams(
            time_s=data["time"]["data"],
            distance_m=data.get("distance", {}).get("data", []),
            velocity_m_s=data["velocity_smooth"]["data"],
            grade_pct=data.get("grade_smooth", {}).get("data"),
            heart_rate=data.get("heartrate", {}).get("data"),
            cadence=data.get("cadence", {}).get("data"),
        )


async def refresh_access_token(refresh_token: str) -> dict:
    """Vrátí {access_token, refresh_token, expires_at}."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


# TODO: fit_personal_gap_curve(streams) a fit_personal_fatigue(activities) ->
# regrese osobní GAP křivky a únavového koeficientu, uložit do Runner.model_params.
