from app.db import _engine_kwargs, normalize_db_url


def test_supabase_raw_url_gets_psycopg_driver():
    raw = "postgresql://postgres.ref:pw@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
    assert normalize_db_url(raw).startswith("postgresql+psycopg://")


def test_postgres_short_scheme_normalized():
    assert normalize_db_url("postgres://u:p@host:5432/db").startswith("postgresql+psycopg://")


def test_already_qualified_url_unchanged():
    url = "postgresql+psycopg://u:p@host/db"
    assert normalize_db_url(url) == url


def test_sqlite_url_unchanged():
    url = "sqlite:///D:/AI/tracking/backend/tracking.db"
    assert normalize_db_url(url) == url


def test_engine_kwargs_sqlite_vs_postgres():
    sqlite_kwargs = _engine_kwargs("sqlite:///x.db")
    assert sqlite_kwargs["connect_args"]["check_same_thread"] is False
    assert "pool_pre_ping" not in sqlite_kwargs

    pg_kwargs = _engine_kwargs("postgresql+psycopg://u:p@h/db")
    assert pg_kwargs["pool_pre_ping"] is True
    # Prepared statements vypnuté -> funguje i přes transaction pooler
    assert pg_kwargs["connect_args"]["prepare_threshold"] is None
    assert pg_kwargs["connect_args"]["sslmode"] == "require"
