"""Počasí podél trasy přes Open-Meteo (zdarma, bez API klíče).

Pro skeleton: jedna předpověď pro střed trasy, faktor per segment podle
hodiny predikovaného průchodu. Později: dotazy pro více bodů dlouhé trasy.
"""

from datetime import datetime, timedelta, timezone

import httpx
import numpy as np

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_hourly_forecast(lat: float, lon: float) -> dict | None:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,snowfall,visibility",
        "forecast_days": 3,
        "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            return resp.json()["hourly"]
    except (httpx.HTTPError, KeyError):
        return None


def weather_factor(temp_c: float, precip_mm: float, snow_cm: float, visibility_m: float | None) -> float:
    factor = 1.0
    if temp_c > 15.0:
        factor += (temp_c - 15.0) * 0.01  # horko: ~1 % na stupeň
    if precip_mm > 0.5:
        factor += 0.05  # déšť / bláto na trailu
    if snow_cm > 0.1:
        factor += 0.15
    if visibility_m is not None and visibility_m < 200:
        factor += 0.08  # mlha
    return factor


def factors_for_segments(
    segments: list[dict],
    race_start: datetime,
    eta_seconds: np.ndarray,
    hourly: dict | None,
) -> np.ndarray:
    """Faktor per segment podle předpovědi v hodině predikovaného průchodu."""
    if hourly is None:
        return np.ones(len(segments))
    if race_start.tzinfo is None:
        race_start = race_start.replace(tzinfo=timezone.utc)

    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in hourly["time"]]
    factors = np.ones(len(segments))
    for i in range(len(segments)):
        ts = race_start + timedelta(seconds=float(eta_seconds[i]))
        idx = min(range(len(times)), key=lambda j: abs((times[j] - ts).total_seconds()))
        factors[i] = weather_factor(
            temp_c=hourly["temperature_2m"][idx],
            precip_mm=hourly["precipitation"][idx],
            snow_cm=hourly.get("snowfall", [0] * len(times))[idx],
            visibility_m=(hourly.get("visibility") or [None] * len(times))[idx],
        )
    return factors
