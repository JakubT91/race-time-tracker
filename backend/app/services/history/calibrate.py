"""Osobní kalibrace modelu ze Strava historie.

Ze streams (tempo + sklon + tep vzorek po vzorku) se počítá:
  - gap_uphill_scale / gap_downhill_scale: jak se běžec liší od Minettiho křivky
  - fatigue_k: pokles GAP tempa mezi první a druhou polovinou dlouhých běhů
  - hr_threshold: odhad prahového tepu (pro budoucí kardiální drift)

Výstup jde do Runner.model_params — predikční engine si klíče převezme jako overrides.
"""

import numpy as np

from app.services.history.base import ActivityStreams
from app.services.prediction.gap import gap_factor

MIN_SPEED_M_S = 0.7  # pomalejší vzorky = stání/chůze v davu, do kalibrace nepatří
LONG_RUN_KM = 18.0  # od kdy běh vypovídá o únavě
FATIGUE_SENSITIVITY = 2.0  # ratio polovin -> k (odvozeno z tvaru 1 + k*frac^1.7)


def _collect_samples(activities: list[ActivityStreams]) -> tuple[np.ndarray, np.ndarray]:
    """Všechny (grade decimální, pace s/m) vzorky napříč aktivitami."""
    grades, paces = [], []
    for act in activities:
        if not act.grade_pct or not act.velocity_m_s:
            continue
        v = np.asarray(act.velocity_m_s, dtype=float)
        g = np.asarray(act.grade_pct, dtype=float) / 100.0
        n = min(len(v), len(g))
        v, g = v[:n], g[:n]
        mask = v > MIN_SPEED_M_S
        grades.append(g[mask])
        paces.append(1.0 / v[mask])
    if not grades:
        return np.array([]), np.array([])
    return np.concatenate(grades), np.concatenate(paces)


def fit_gap_scales(activities: list[ActivityStreams]) -> dict:
    """Porovná skutečné zpomalení v binech sklonu s Minettim -> osobní škály."""
    grades, paces = _collect_samples(activities)
    if len(grades) < 5000:
        return {}  # málo dat na věrohodnou křivku

    flat = paces[np.abs(grades) < 0.01]
    if len(flat) < 500:
        return {}
    flat_pace = float(np.median(flat))

    def scale_for(bins: np.ndarray) -> float | None:
        ratios, weights = [], []
        for lo, hi in zip(bins[:-1], bins[1:]):
            mask = (grades >= lo) & (grades < hi)
            if mask.sum() < 300:
                continue
            observed_dev = float(np.median(paces[mask])) / flat_pace - 1.0
            model_dev = float(gap_factor((lo + hi) / 2)) - 1.0
            if abs(model_dev) < 0.02:
                continue
            ratios.append(observed_dev / model_dev)
            weights.append(mask.sum())
        if not ratios:
            return None
        return float(np.clip(np.average(ratios, weights=weights), 0.4, 2.0))

    result = {}
    up = scale_for(np.arange(0.02, 0.26, 0.02))
    down = scale_for(np.arange(-0.24, 0.0, 0.02))
    if up is not None:
        result["gap_uphill_scale"] = up
    if down is not None:
        result["gap_downhill_scale"] = down
    return result


def fit_fatigue(activities: list[ActivityStreams]) -> dict:
    """Z dlouhých běhů: o kolik je GAP tempo druhé poloviny pomalejší než první."""
    ks = []
    for act in activities:
        if not act.distance_m or not act.velocity_m_s:
            continue
        d = np.asarray(act.distance_m, dtype=float)
        v = np.asarray(act.velocity_m_s, dtype=float)
        n = min(len(d), len(v))
        d, v = d[:n], v[:n]
        if d[-1] < LONG_RUN_KM * 1000:
            continue

        pace = np.where(v > MIN_SPEED_M_S, 1.0 / np.maximum(v, MIN_SPEED_M_S), np.nan)
        if act.grade_pct:
            g = np.asarray(act.grade_pct[:n], dtype=float) / 100.0
            pace = pace / gap_factor(g)  # očištění o sklon

        half = d[-1] / 2
        first = np.nanmedian(pace[d < half])
        second = np.nanmedian(pace[d >= half])
        if not (np.isfinite(first) and np.isfinite(second)) or first <= 0:
            continue
        ks.append(FATIGUE_SENSITIVITY * (second / first - 1.0))

    if len(ks) < 2:
        return {}
    return {"fatigue_k": float(np.clip(np.median(ks), 0.02, 0.6))}


def fit_hr_threshold(activities: list[ActivityStreams]) -> dict:
    """Hrubý odhad prahového tepu: 92. percentil HR napříč delšími běhy."""
    hrs = [
        np.asarray(act.heart_rate, dtype=float)
        for act in activities
        if act.heart_rate and act.time_s and act.time_s[-1] > 40 * 60
    ]
    if not hrs:
        return {}
    all_hr = np.concatenate(hrs)
    all_hr = all_hr[all_hr > 60]  # artefakty snímače
    if len(all_hr) < 2000:
        return {}
    return {
        "hr_threshold": float(np.percentile(all_hr, 92)),
        "hr_max_observed": float(all_hr.max()),
    }


def calibrate_from_history(activities: list[ActivityStreams]) -> dict:
    params: dict = {}
    params.update(fit_gap_scales(activities))
    params.update(fit_fatigue(activities))
    params.update(fit_hr_threshold(activities))
    params["history_activities_used"] = len(activities)
    return params
