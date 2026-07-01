"""GPX -> vyhlazený profil -> segmenty po ~100 m se sklonem."""

from dataclasses import dataclass

import gpxpy
import numpy as np

EARTH_RADIUS_M = 6_371_000.0


@dataclass
class Segment:
    start_m: float
    end_m: float
    grade: float  # decimální sklon, 0.10 = 10 % do kopce
    ele: float  # nadmořská výška středu segmentu
    lat: float
    lon: float

    def to_dict(self) -> dict:
        return {
            "start_m": round(self.start_m, 1),
            "end_m": round(self.end_m, 1),
            "grade": round(self.grade, 4),
            "ele": round(self.ele, 1),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
        }


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def parse_gpx(gpx_content: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vrátí (dist_m kumulativně, ele, lat, lon) pro všechny body trasy."""
    gpx = gpxpy.parse(gpx_content)
    lats, lons, eles = [], [], []
    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                lats.append(p.latitude)
                lons.append(p.longitude)
                eles.append(p.elevation if p.elevation is not None else np.nan)
    if not lats and gpx.routes:
        for route in gpx.routes:
            for p in route.points:
                lats.append(p.latitude)
                lons.append(p.longitude)
                eles.append(p.elevation if p.elevation is not None else np.nan)
    if len(lats) < 2:
        raise ValueError("GPX neobsahuje použitelnou trasu (track ani route)")

    lat = np.asarray(lats)
    lon = np.asarray(lons)
    ele = np.asarray(eles, dtype=float)

    # Chybějící výšky doplníme interpolací
    if np.isnan(ele).any():
        idx = np.arange(len(ele))
        valid = ~np.isnan(ele)
        if not valid.any():
            raise ValueError("GPX neobsahuje výšková data")
        ele = np.interp(idx, idx[valid], ele[valid])

    step = haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dist = np.concatenate([[0.0], np.cumsum(step)])
    return dist, ele, lat, lon


def smooth_elevation(ele: np.ndarray, window: int = 11) -> np.ndarray:
    """Klouzavý medián + průměr — surová GPX výška je zašuměná a nafukuje převýšení."""
    if len(ele) < window:
        return ele
    pad = window // 2
    padded = np.pad(ele, pad, mode="edge")
    med = np.array([np.median(padded[i : i + window]) for i in range(len(ele))])
    kernel = np.ones(window) / window
    return np.convolve(np.pad(med, pad, mode="edge"), kernel, mode="valid")


def build_segments(gpx_content: str, segment_length_m: float = 100.0) -> tuple[list[Segment], float, float]:
    """Vrátí (segmenty, celková vzdálenost, celkové převýšení)."""
    dist, ele, lat, lon = parse_gpx(gpx_content)
    ele = smooth_elevation(ele)
    total = float(dist[-1])
    if total < segment_length_m * 2:
        raise ValueError("Trasa je příliš krátká")

    grid = np.arange(0.0, total, segment_length_m)
    grid = np.append(grid, total)
    ele_g = np.interp(grid, dist, ele)
    lat_g = np.interp(grid, dist, lat)
    lon_g = np.interp(grid, dist, lon)

    segments = []
    for i in range(len(grid) - 1):
        length = grid[i + 1] - grid[i]
        if length <= 0:
            continue
        grade = (ele_g[i + 1] - ele_g[i]) / length
        segments.append(
            Segment(
                start_m=float(grid[i]),
                end_m=float(grid[i + 1]),
                grade=float(np.clip(grade, -0.45, 0.45)),
                ele=float((ele_g[i] + ele_g[i + 1]) / 2),
                lat=float((lat_g[i] + lat_g[i + 1]) / 2),
                lon=float((lon_g[i] + lon_g[i + 1]) / 2),
            )
        )

    ascent = float(np.sum(np.clip(np.diff(ele_g), 0, None)))
    return segments, total, ascent


def downsample_profile(segments: list[dict], max_points: int = 400) -> list[dict]:
    """Profil pro frontend — graf nepotřebuje tisíce bodů."""
    stride = max(1, -(-len(segments) // max_points))
    pts = [
        {"km": s["start_m"] / 1000.0, "ele": s["ele"]}
        for s in segments[::stride]
    ]
    last = segments[-1]
    pts.append({"km": last["end_m"] / 1000.0, "ele": last["ele"]})
    return pts
