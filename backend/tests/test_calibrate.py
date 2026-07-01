import numpy as np

from app.services.history.base import ActivityStreams
from app.services.history.calibrate import calibrate_from_history, fit_fatigue, fit_gap_scales
from app.services.prediction.engine import SimulationParams, personal_gap_factor
from app.services.prediction.gap import gap_factor


def synthetic_activity(
    n: int = 8000,
    uphill_scale: float = 1.0,
    fatigue_ratio: float = 1.0,
    distance_km: float = 30.0,
    seed: int = 0,
) -> ActivityStreams:
    """Běžec přesně podle Minettiho * uphill_scale, druhá polovina pomalejší o fatigue_ratio."""
    rng = np.random.default_rng(seed)
    grade = rng.uniform(-0.20, 0.20, size=n)
    flat_v = 3.0  # m/s na rovině
    factor = 1.0 + (gap_factor(grade) - 1.0) * uphill_scale
    v = flat_v / factor
    half = n // 2
    v[half:] /= fatigue_ratio
    dist = np.cumsum(np.full(n, distance_km * 1000 / n))
    return ActivityStreams(
        time_s=list(np.cumsum(1.0 / v)),
        distance_m=list(dist),
        velocity_m_s=list(v),
        grade_pct=list(grade * 100),
        heart_rate=list(rng.normal(150, 12, size=n)),
        cadence=None,
    )


def test_fit_gap_scales_recovers_scale():
    acts = [synthetic_activity(uphill_scale=1.4, seed=i) for i in range(3)]
    scales = fit_gap_scales(acts)
    assert 1.2 < scales["gap_uphill_scale"] < 1.6
    assert 1.1 < scales["gap_downhill_scale"] < 1.7


def test_fit_fatigue_detects_slowdown():
    acts = [synthetic_activity(fatigue_ratio=1.10, seed=i) for i in range(3)]
    result = fit_fatigue(acts)
    assert 0.1 < result["fatigue_k"] < 0.35  # ratio 1.10 -> k ~ 0.2


def test_calibrate_from_history_combines():
    acts = [synthetic_activity(seed=i) for i in range(3)]
    params = calibrate_from_history(acts)
    assert params["history_activities_used"] == 3
    assert "hr_threshold" in params
    assert 130 < params["hr_threshold"] < 190


def test_personal_gap_factor_scales_deviation():
    params_avg = SimulationParams(base_pace_s_per_km=300.0)
    params_climber = SimulationParams(base_pace_s_per_km=300.0, gap_uphill_scale=0.7)
    grades = np.array([0.10])
    avg = personal_gap_factor(grades, params_avg)[0]
    climber = personal_gap_factor(grades, params_climber)[0]
    assert climber < avg  # lepší vrchař zpomaluje do kopce méně
    assert abs((climber - 1.0) / (avg - 1.0) - 0.7) < 1e-9
