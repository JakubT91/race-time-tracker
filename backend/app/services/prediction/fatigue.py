"""Postupná únava: multiplikátor tempa rostoucí s uběhnutým podílem trasy.

factor = 1 + k * frac^p
k ... celkové zpomalení na konci (0.25 = o 25 % pomaleji v cíli než na startu)
p ... tvar křivky (>1 = únava nastupuje později, ale strměji)

k a p se rekalibrují za závodu z reálného tempa a tepu (kardiální drift).
"""

import numpy as np


def fatigue_factor(progress_frac: np.ndarray | float, k: float = 0.25, p: float = 1.7):
    return 1.0 + k * np.power(np.clip(progress_frac, 0.0, 1.0), p)


def feel_to_adjustment(feel: int) -> tuple[float, float]:
    """Subjektivní pocit 1–5 -> (posun středu tempa, multiplikátor rozptylu).

    1 = skvělá forma (mírně rychlejší, užší rozptyl), 5 = špatná (pomalejší, širší rozptyl).
    """
    shift = {1: -0.02, 2: -0.01, 3: 0.0, 4: 0.03, 5: 0.07}[feel]
    sigma_mult = {1: 0.8, 2: 0.9, 3: 1.0, 4: 1.25, 5: 1.5}[feel]
    return shift, sigma_mult
