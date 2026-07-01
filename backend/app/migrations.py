"""Lehké idempotentní migrace při startu (bez Alembicu).

create_all vytvoří chybějící tabulky, ale nepřidá nový sloupec do existující —
o owner_id u races se proto staráme ručně. Funguje pro SQLite i Postgres.
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db import Base

log = logging.getLogger(__name__)


def run_migrations(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    _ensure_column(engine, "races", "owner_id", "INTEGER")
    _ensure_column(engine, "users", "last_login_at", "TIMESTAMP")


def _ensure_column(engine: Engine, table: str, column: str, sql_type: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}'))
    log.info("Migrace: přidán sloupec %s.%s", table, column)
