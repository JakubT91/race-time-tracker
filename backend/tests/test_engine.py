import numpy as np

from app.services.prediction.engine import (
    SimulationParams,
    calibrate_base_pace,
    simulate,
)
from app.services.prediction.gap import gap_factor


def flat_segments(total_km: float = 50.0, seg_m: float = 100.0) -> list[dict]:
    n = int(total_km * 1000 / seg_m)
    return [
        {
            "start_m": i * seg_m,
            "end_m": (i + 1) * seg_m,
            "grade": 0.0,
            "ele": 500.0,
            "lat": 49.0,
            "lon": 16.6,
        }
        for i in range(n)
    ]


def test_gap_factor_flat_is_one():
    assert abs(float(gap_factor(0.0)) - 1.0) < 1e-9


def test_gap_factor_uphill_slower_downhill_capped():
    assert float(gap_factor(0.10)) > 1.4  # 10 % do kopce výrazně zpomaluje
    assert float(gap_factor(-0.05)) >= 0.85


def test_calibration_hits_target():
    segments = flat_segments()
    target = 5 * 3600.0
    params = SimulationParams(base_pace_s_per_km=1.0, n_runs=500, seed=1)
    params.base_pace_s_per_km = calibrate_base_pace(segments, target, params)

    result = simulate(segments, params)
    # Medián cílového času musí být blízko cílovému času (šum simulace je malý)
    assert abs(result.finish["p50"] - target) / target < 0.05


def test_percentiles_ordered_and_growing():
    segments = flat_segments(total_km=20)
    params = SimulationParams(base_pace_s_per_km=360.0, n_runs=500, seed=2)
    result = simulate(segments, params)

    assert result.finish["p10"] < result.finish["p50"] < result.finish["p90"]
    medians = [p["p50"] for p in result.per_km]
    assert all(a < b for a, b in zip(medians, medians[1:]))
    assert len(result.per_km) == 20


def test_aid_station_adds_stop_time():
    segments = flat_segments(total_km=20)
    base = SimulationParams(base_pace_s_per_km=360.0, n_runs=800, seed=3)
    with_stop = SimulationParams(
        base_pace_s_per_km=360.0,
        n_runs=800,
        seed=3,
        aid_stations=[{"name": "AS1", "distance_m": 10_000.0, "expected_stop_s": 300.0}],
    )
    no_stop = simulate(segments, base)
    stopped = simulate(segments, with_stop)

    diff = stopped.finish["p50"] - no_stop.finish["p50"]
    assert 150 < diff < 600  # ~5 min zastávka se propíše do cíle

    # km 5 (před zastávkou) se nemění, km 15 (za ní) ano
    km5_diff = stopped.per_km[4]["p50"] - no_stop.per_km[4]["p50"]
    km15_diff = stopped.per_km[14]["p50"] - no_stop.per_km[14]["p50"]
    assert abs(km5_diff) < 30
    assert km15_diff > 150


def test_fatigue_slows_second_half():
    segments = flat_segments(total_km=40)
    params = SimulationParams(base_pace_s_per_km=360.0, fatigue_k=0.3, n_runs=500, seed=4)
    result = simulate(segments, params)
    first_half = result.per_km[19]["p50"]
    second_half = result.finish["p50"] - first_half
    assert second_half > first_half * 1.05
