import numpy as np
import pytest

from app.services.route_service import build_segments, downsample_profile, smooth_elevation


def synthetic_gpx(n_points: int = 200) -> str:
    """~10 km na sever s kopcem uprostřed."""
    points = []
    for i in range(n_points):
        lat = 49.0 + i * 0.0005  # ~55 m na krok
        ele = 500 + 200 * np.sin(np.pi * i / n_points)
        points.append(f'<trkpt lat="{lat}" lon="16.6"><ele>{ele:.1f}</ele></trkpt>')
    return (
        '<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{''.join(points)}</trkseg></trk></gpx>"
    )


def test_build_segments_basic():
    segments, total, ascent = build_segments(synthetic_gpx(), segment_length_m=100.0)
    assert total > 9000
    assert 150 < ascent < 250  # sinusovka stoupá o ~200 m
    assert all(s.end_m > s.start_m for s in segments)
    assert abs(segments[-1].end_m - total) < 1.0
    # První polovina stoupá, druhá klesá
    mid = len(segments) // 2
    assert np.mean([s.grade for s in segments[: mid // 2]]) > 0
    assert np.mean([s.grade for s in segments[mid + mid // 2 :]]) < 0


def test_build_segments_rejects_short_route():
    with pytest.raises(ValueError):
        build_segments(synthetic_gpx(n_points=3), segment_length_m=100.0)


def test_smooth_elevation_reduces_noise():
    rng = np.random.default_rng(42)
    clean = np.linspace(500, 700, 500)
    noisy = clean + rng.normal(0, 5, size=500)
    smoothed = smooth_elevation(noisy)
    assert np.std(smoothed - clean) < np.std(noisy - clean)


def test_downsample_profile_caps_points():
    segments, _, _ = build_segments(synthetic_gpx(2000), segment_length_m=100.0)
    profile = downsample_profile([s.to_dict() for s in segments], max_points=400)
    assert len(profile) <= 402
    assert profile[0]["km"] == 0.0
