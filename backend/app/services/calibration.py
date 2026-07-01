"""Rekalibrace modelu za závodu z reálných trackpointů.

Princip: porovnáme skutečné grade-adjusted tempo se základním tempem modelu
a bayesovsky posuneme odhad. Váha pozorování roste s uběhnutou vzdáleností,
takže predikce se s postupem závodu zpřesňuje a pásmo nejistoty zužuje.

Tep (kardiální drift) je připravený jako další signál — viz TODO níže.
"""

import numpy as np

from app.services.prediction.fatigue import fatigue_factor
from app.services.prediction.gap import gap_factor

# Kolik km musí běžec mít, aby pozorování plně převážilo prior z cílového času
FULL_TRUST_KM = 30.0


def observed_base_pace(
    segments: list[dict],
    track: list[dict],
    fatigue_k: float,
    fatigue_p: float,
) -> float | None:
    """Z trackpointů [{route_distance_m, timestamp_s, is_paused}] spočte rovinkové tempo běžce.

    elapsed = base_pace * suma(délka * gap * únava) přes proběhnuté segmenty -> base_pace.
    """
    moving = [t for t in track if t.get("route_distance_m") is not None and not t.get("is_paused")]
    if len(moving) < 5:
        return None
    moving.sort(key=lambda t: t["timestamp_s"])
    covered_m = moving[-1]["route_distance_m"]
    elapsed_s = moving[-1]["timestamp_s"] - moving[0]["timestamp_s"]
    if covered_m < 1000 or elapsed_s <= 0:
        return None

    total = segments[-1]["end_m"]
    done = [s for s in segments if s["end_m"] <= covered_m]
    if not done:
        return None
    grades = np.array([s["grade"] for s in done])
    lengths_km = np.array([(s["end_m"] - s["start_m"]) / 1000.0 for s in done])
    mids = np.array([(s["start_m"] + s["end_m"]) / 2 for s in done])

    weighted_km = float(np.sum(lengths_km * gap_factor(grades) * fatigue_factor(mids / total, fatigue_k, fatigue_p)))
    if weighted_km <= 0:
        return None
    return elapsed_s / weighted_km


def recalibrate(
    segments: list[dict],
    track: list[dict],
    prior_base_pace: float,
    fatigue_k: float = 0.25,
    fatigue_p: float = 1.7,
) -> dict:
    """Vrátí overrides pro SimulationParams: posunuté tempo + zúžená nejistota.

    TODO: kardiální drift — rostoucí HR při stejném GAP tempu => zvýšit fatigue_k
    dřív, než se únava projeví na tempu. Vyžaduje threshold HR z historie (Strava).
    """
    observed = observed_base_pace(segments, track, fatigue_k, fatigue_p)
    if observed is None:
        return {}

    covered_km = max(t.get("route_distance_m") or 0 for t in track) / 1000.0
    weight = min(covered_km / FULL_TRUST_KM, 0.9)

    blended = (1 - weight) * prior_base_pace + weight * observed
    sigma = 0.06 * (1 - 0.6 * weight)  # nejistota klesá s ujetými km
    return {
        "base_pace_s_per_km": float(blended),
        "base_pace_sigma": float(sigma),
    }
