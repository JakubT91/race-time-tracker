"""Grade-adjusted pace — kolikrát pomaleji běžec poběží daný sklon oproti rovině.

Vychází z Minettiho energetických nákladů běhu (Minetti et al. 2002, J Appl Physiol):
C(i) = 155.4 i^5 - 30.4 i^4 - 43.3 i^3 + 46.3 i^2 + 19.5 i + 3.6  [J/kg/m]
Faktor = C(i) / C(0). Po napojení Strava historie běžce se nahradí osobní křivkou.
"""

import numpy as np

_COEFFS = np.array([155.4, -30.4, -43.3, 46.3, 19.5, 3.6])
_FLAT_COST = 3.6


def gap_factor(grade: np.ndarray | float) -> np.ndarray | float:
    """grade: decimální sklon (0.1 = 10 % do kopce). Vrací multiplikátor tempa >= ~0.9."""
    i = np.clip(grade, -0.45, 0.45)
    cost = np.polyval(_COEFFS, i)
    factor = cost / _FLAT_COST
    # Energeticky je mírný seběh "zadarmo", prakticky technika limituje — nepouštíme pod 0.85
    return np.maximum(factor, 0.85)
