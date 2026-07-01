"""Smoke test proti běžícímu backendu: závod -> GPX -> občerstvovačky -> běžec -> predikce.

Spuštění: python tests/e2e_smoke.py (vyžaduje uvicorn na :8000)
"""

import io
import sys

import httpx
import numpy as np

BASE = "http://localhost:8000"


def synthetic_gpx(n_points: int = 1200) -> str:
    points = []
    for i in range(n_points):
        lat = 49.0 + i * 0.0005
        ele = 500 + 400 * np.sin(2 * np.pi * i / n_points) + 150 * np.sin(8 * np.pi * i / n_points)
        points.append(f'<trkpt lat="{lat}" lon="16.6"><ele>{ele:.1f}</ele></trkpt>')
    return (
        '<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{''.join(points)}</trkseg></trk></gpx>"
    )


def fmt(s: float) -> str:
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}"


def main() -> int:
    client = httpx.Client(timeout=60)

    health = client.get(f"{BASE}/health").json()
    assert health["status"] == "ok"

    race = client.post(
        f"{BASE}/races", json={"name": "Test ultra", "start_time": "2026-08-15T05:00:00Z"}
    ).json()
    print(f"Závod: {race['name']} (id {race['id']})")

    gpx = synthetic_gpx()
    resp = client.post(
        f"{BASE}/races/{race['id']}/gpx",
        files={"file": ("test.gpx", io.BytesIO(gpx.encode()), "application/gpx+xml")},
    )
    resp.raise_for_status()
    race = resp.json()
    print(f"Trasa: {race['total_distance_m'] / 1000:.1f} km, převýšení {race['total_ascent_m']:.0f} m")

    stations = client.post(
        f"{BASE}/races/{race['id']}/aid-stations",
        json=[
            {"name": "AS1", "distance_m": 20_000, "expected_stop_s": 180},
            {"name": "AS2", "distance_m": 45_000, "expected_stop_s": 420},
        ],
    )
    stations.raise_for_status()

    runner = client.post(
        f"{BASE}/races/{race['id']}/runners",
        json={"name": "Testovací běžec", "target_time_s": 8 * 3600, "feel": 3},
    ).json()

    pred = client.post(f"{BASE}/runners/{runner['id']}/predict")
    pred.raise_for_status()
    p = pred.json()

    finish = p["finish"]
    print(f"Cíl: {fmt(finish['p50'])} (P10 {fmt(finish['p10'])} – P90 {fmt(finish['p90'])})")
    for a in p["aid_stations"]:
        print(f"  {a['name']} @ km {a['distance_m'] / 1000:.0f}: {fmt(a['p50'])} ({fmt(a['p10'])}–{fmt(a['p90'])})")
    print(f"Predikce po km: {len(p['per_km'])} záznamů")

    assert finish["p10"] < finish["p50"] < finish["p90"]
    # Cílový čas 8 h: medián musí být poblíž (kalibrace) — tma/počasí ho můžou posunout
    assert abs(finish["p50"] - 8 * 3600) < 0.15 * 8 * 3600
    assert len(p["per_km"]) >= 60

    latest = client.get(f"{BASE}/runners/{runner['id']}/prediction/latest")
    latest.raise_for_status()

    print("Smoke test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
