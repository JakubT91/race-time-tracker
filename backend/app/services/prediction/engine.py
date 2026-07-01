"""Monte Carlo simulace průchodu trasou.

Každý běh navzorkuje nejistoty (základní tempo, únavový koeficient, zastávky,
počasí) a projde segmenty; z N běhů vzniknou percentily času průchodu každým km.
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.services.darkness import darkness_factors
from app.services.prediction.fatigue import fatigue_factor, feel_to_adjustment
from app.services.prediction.gap import gap_factor


@dataclass
class SimulationParams:
    base_pace_s_per_km: float  # rovinkové tempo, kalibrované z cílového času
    base_pace_sigma: float = 0.06  # relativní nejistota tempa
    fatigue_k: float = 0.25
    fatigue_k_sigma: float = 0.08
    fatigue_p: float = 1.7
    feel: int = 3
    # Osobní GAP křivka (ze Strava historie): škálování odchylky Minettiho faktoru od 1.0.
    # 1.0 = průměrný běžec, <1 = lepší vrchař/sběhař než model, >1 = horší.
    gap_uphill_scale: float = 1.0
    gap_downhill_scale: float = 1.0
    # Faktory prostředí per segment (1.0 = neutrální); plní weather/darkness služby
    weather_factors: np.ndarray | None = None
    darkness: np.ndarray | None = None
    aid_stations: list[dict] = field(default_factory=list)  # {distance_m, expected_stop_s}
    n_runs: int = 2000
    seed: int | None = None


@dataclass
class SimulationResult:
    finish: dict  # {p10, p50, p90} v sekundách od startu
    per_km: list[dict]  # [{km, p10, p50, p90}]
    aid_stations: list[dict]


def _percentiles(samples: np.ndarray) -> dict:
    p10, p50, p90 = np.percentile(samples, [10, 50, 90])
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90)}


def personal_gap_factor(grades: np.ndarray, params: SimulationParams) -> np.ndarray:
    """Minettiho GAP s osobním škálováním do/z kopce z historie běžce."""
    base = gap_factor(grades)
    scale = np.where(np.asarray(grades) >= 0, params.gap_uphill_scale, params.gap_downhill_scale)
    return np.maximum(1.0 + (base - 1.0) * scale, 0.7)


def deterministic_seconds_per_segment(segments: list[dict], params: SimulationParams) -> np.ndarray:
    """Střední čas na segment bez šumu — používá se i pro kalibraci tempa z cílového času."""
    grades = np.array([s["grade"] for s in segments])
    lengths_km = np.array([(s["end_m"] - s["start_m"]) / 1000.0 for s in segments])
    mids = np.array([(s["start_m"] + s["end_m"]) / 2 for s in segments])
    total = segments[-1]["end_m"]

    factors = personal_gap_factor(grades, params) * fatigue_factor(mids / total, params.fatigue_k, params.fatigue_p)
    if params.weather_factors is not None:
        factors = factors * params.weather_factors
    if params.darkness is not None:
        factors = factors * params.darkness
    return params.base_pace_s_per_km * lengths_km * factors


def calibrate_base_pace(segments: list[dict], target_time_s: float, params: SimulationParams) -> float:
    """Najde rovinkové tempo tak, aby deterministický průchod dal cílový čas.

    Model je v base_pace lineární: total = base_pace * S + zastávky.
    """
    probe = SimulationParams(**{**params.__dict__, "base_pace_s_per_km": 1.0})
    s = float(np.sum(deterministic_seconds_per_segment(segments, probe)))
    stops = sum(a["expected_stop_s"] for a in params.aid_stations)
    moving_target = max(target_time_s - stops, 1.0)
    return moving_target / s


def simulate(segments: list[dict], params: SimulationParams) -> SimulationResult:
    rng = np.random.default_rng(params.seed)
    n = params.n_runs

    grades = np.array([s["grade"] for s in segments])
    lengths_km = np.array([(s["end_m"] - s["start_m"]) / 1000.0 for s in segments])
    mids = np.array([(s["start_m"] + s["end_m"]) / 2 for s in segments])
    ends = np.array([s["end_m"] for s in segments])
    total = float(ends[-1])
    n_seg = len(segments)

    feel_shift, sigma_mult = feel_to_adjustment(params.feel)

    base = params.base_pace_s_per_km * (1.0 + feel_shift)
    sigma = params.base_pace_sigma * sigma_mult
    base_pace = rng.normal(base, base * sigma, size=n)  # (n,)
    fatigue_k = np.clip(rng.normal(params.fatigue_k, params.fatigue_k_sigma, size=n), 0.0, 1.5)

    # Per-segment deterministické faktory (n_seg,)
    seg_factor = personal_gap_factor(grades, params)
    if params.weather_factors is not None:
        seg_factor = seg_factor * params.weather_factors
    if params.darkness is not None:
        seg_factor = seg_factor * params.darkness

    # (n, n_seg): únava závisí na navzorkovaném k
    fat = 1.0 + fatigue_k[:, None] * np.power(mids[None, :] / total, params.fatigue_p)
    seconds = base_pace[:, None] * lengths_km[None, :] * seg_factor[None, :] * fat

    # Šum jednotlivých segmentů (terén, mikro-zastávky) — nezávislý, relativně malý
    seconds *= rng.normal(1.0, 0.03, size=seconds.shape)

    cumulative = np.cumsum(seconds, axis=1)  # (n, n_seg) čas na konci segmentu

    # Zastávky na občerstvovačkách: lognormální kolem očekávané délky
    for station in sorted(params.aid_stations, key=lambda a: a["distance_m"]):
        mean_stop = max(float(station["expected_stop_s"]), 1.0)
        stops = rng.lognormal(np.log(mean_stop), 0.4, size=n)
        affected = ends >= station["distance_m"]
        cumulative[:, affected] += stops[:, None]

    # Percentily na celých km
    km_marks = np.arange(1.0, np.floor(total / 1000.0) + 1)
    per_km = []
    for km in km_marks:
        idx = int(np.searchsorted(ends, km * 1000.0))
        idx = min(idx, n_seg - 1)
        per_km.append({"km": float(km), **_percentiles(cumulative[:, idx])})

    aid_out = [
        {
            "name": a.get("name", f"AS {i + 1}"),
            "distance_m": float(a["distance_m"]),
            **_percentiles(cumulative[:, min(int(np.searchsorted(ends, a["distance_m"])), n_seg - 1)]),
        }
        for i, a in enumerate(sorted(params.aid_stations, key=lambda a: a["distance_m"]))
    ]

    return SimulationResult(
        finish=_percentiles(cumulative[:, -1]),
        per_km=per_km,
        aid_stations=aid_out,
    )


def build_params_for_runner(
    segments: list[dict],
    target_time_s: float,
    feel: int,
    aid_stations: list[dict],
    race_start: datetime | None,
    weather_factors: np.ndarray | None = None,
    overrides: dict | None = None,
    n_runs: int = 2000,
) -> SimulationParams:
    """Sestaví parametry simulace: kalibrace tempa z cílového času + tma + overrides z rekalibrace."""
    params = SimulationParams(
        base_pace_s_per_km=300.0,  # placeholder, hned přepíše kalibrace
        feel=feel,
        aid_stations=aid_stations,
        weather_factors=weather_factors,
        n_runs=n_runs,
    )
    if overrides:
        for key, value in overrides.items():
            if hasattr(params, key) and value is not None:
                setattr(params, key, value)

    if race_start is not None:
        # Iterace: tma závisí na predikovaných časech, časy na tmě. Dvě kola stačí.
        params.base_pace_s_per_km = calibrate_base_pace(segments, target_time_s, params)
        for _ in range(2):
            seconds = deterministic_seconds_per_segment(segments, params)
            eta = np.cumsum(seconds)
            params.darkness = darkness_factors(segments, race_start, eta)
            params.base_pace_s_per_km = calibrate_base_pace(segments, target_time_s, params)
    else:
        params.base_pace_s_per_km = calibrate_base_pace(segments, target_time_s, params)

    if overrides and overrides.get("base_pace_s_per_km"):
        # Rekalibrace za závodu má přednost před kalibrací z cílového času
        params.base_pace_s_per_km = overrides["base_pace_s_per_km"]
    return params
