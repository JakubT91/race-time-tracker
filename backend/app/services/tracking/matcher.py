"""Mapování GPS polohy na staničení trasy (km závodu).

Skeleton: nejbližší střed segmentu přes numpy. Pro trasy, které se kříží nebo
vedou tam a zpět, nahradit PostGIS (ST_LineLocatePoint) + filtrem na monotónní
postup podle posledního známého staničení.
"""

import numpy as np

from app.services.route_service import haversine_m

MAX_OFF_ROUTE_M = 300.0


def match_to_route(
    segments: list[dict],
    lat: float,
    lon: float,
    last_distance_m: float | None = None,
    window_m: float = 5000.0,
) -> float | None:
    """Vrátí staničení (m od startu) nebo None, pokud je běžec daleko od trasy."""
    seg_lat = np.array([s["lat"] for s in segments])
    seg_lon = np.array([s["lon"] for s in segments])
    mids = np.array([(s["start_m"] + s["end_m"]) / 2 for s in segments])

    mask = np.ones(len(segments), dtype=bool)
    if last_distance_m is not None:
        # Hledáme jen v okně kolem poslední polohy — řeší křížící se trasy
        mask = (mids > last_distance_m - window_m / 5) & (mids < last_distance_m + window_m)
        if not mask.any():
            mask = np.ones(len(segments), dtype=bool)

    dists = haversine_m(seg_lat[mask], seg_lon[mask], lat, lon)
    best = int(np.argmin(dists))
    if dists[best] > MAX_OFF_ROUTE_M:
        return None
    return float(mids[mask][best])
