"""Penalizace běhu za tmy — z východu/západu slunce pro souřadnice segmentu."""

from datetime import datetime, timedelta, timezone

import numpy as np
from astral import LocationInfo
from astral.sun import sun

# Zpomalení za tmy; na technickém terénu reálně 5–15 %, skeleton používá paušál
NIGHT_PENALTY = 1.08


def darkness_factors(segments: list[dict], race_start: datetime, eta_seconds: np.ndarray) -> np.ndarray:
    """Pro každý segment 1.0 (den) nebo NIGHT_PENALTY (noc) podle predikovaného času průchodu."""
    if race_start.tzinfo is None:
        race_start = race_start.replace(tzinfo=timezone.utc)

    factors = np.ones(len(segments))
    sun_cache: dict[str, tuple[datetime, datetime]] = {}

    for i, seg in enumerate(segments):
        ts = race_start + timedelta(seconds=float(eta_seconds[i]))
        key = ts.date().isoformat()
        if key not in sun_cache:
            loc = LocationInfo(latitude=seg["lat"], longitude=seg["lon"])
            try:
                s = sun(loc.observer, date=ts.date(), tzinfo=timezone.utc)
                sun_cache[key] = (s["dawn"], s["dusk"])
            except ValueError:
                # Polární den/noc apod. — necháme den
                sun_cache[key] = (ts - timedelta(hours=12), ts + timedelta(hours=12))
        dawn, dusk = sun_cache[key]
        if ts < dawn or ts > dusk:
            factors[i] = NIGHT_PENALTY
    return factors
