from app.services.history.strava import _is_run


def test_accepts_run_and_trailrun():
    assert _is_run({"sport_type": "Run"})
    assert _is_run({"sport_type": "TrailRun"})
    # Starší API objekty bez sport_type
    assert _is_run({"type": "Run"})


def test_rejects_other_sports():
    assert not _is_run({"sport_type": "Ride"})
    assert not _is_run({"sport_type": "VirtualRun"})
    assert not _is_run({"sport_type": "Walk"})
    assert not _is_run({"sport_type": "Hike"})
    assert not _is_run({"type": "Ride"})
    assert not _is_run({})
