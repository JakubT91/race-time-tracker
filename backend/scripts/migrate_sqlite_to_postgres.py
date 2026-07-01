"""Přenos dat z lokální SQLite do cílové Postgres/Supabase databáze.

Použití (z adresáře backend/, s aktivním .venv):
    # cíl = Supabase Session pooler connection string
    python scripts/migrate_sqlite_to_postgres.py "postgresql://postgres.<ref>:<heslo>@...pooler.supabase.com:5432/postgres"

Volitelně lze zdrojovou SQLite zadat 2. argumentem (jinak backend/tracking.db).

Skript: vytvoří tabulky v cíli, zkopíruje všechny řádky v pořadí respektujícím
cizí klíče, zachová primární klíče a nakonec srovná Postgres sekvence, aby se
nové záznamy nekřížily se zkopírovanými ID.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, normalize_db_url  # noqa: E402
from app.models import (  # noqa: E402
    AidStation,
    PredictionRun,
    Race,
    Runner,
    SyncedActivity,
    Trackpoint,
)

# Pořadí podle cizích klíčů: rodiče první
MODELS_IN_ORDER = [Race, AidStation, Runner, Trackpoint, PredictionRun, SyncedActivity]


def main() -> int:
    if len(sys.argv) < 2:
        print("Chybí cílový connection string. Viz docstring na začátku souboru.")
        return 1

    target_url = normalize_db_url(sys.argv[1])
    source_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).resolve().parent.parent / "tracking.db")
    source_url = f"sqlite:///{Path(source_path).as_posix()}"

    print(f"Zdroj: {source_url}")
    print(f"Cíl:   {target_url.split('@')[-1]}")  # heslo neukazujeme

    src = create_engine(source_url, connect_args={"check_same_thread": False})
    dst = create_engine(target_url, connect_args={"prepare_threshold": None, "sslmode": "require"})

    Base.metadata.create_all(dst)

    total = 0
    with Session(src) as s_src, Session(dst) as s_dst:
        for model in MODELS_IN_ORDER:
            rows = s_src.execute(select(model)).scalars().all()
            count = 0
            for row in rows:
                data = {c.key: getattr(row, c.key) for c in model.__table__.columns}
                s_dst.merge(model(**data))  # merge = idempotentní (lze spustit opakovaně)
                count += 1
            s_dst.commit()
            print(f"  {model.__tablename__}: {count} řádků")
            total += count

        # Srovnání sekvencí (jen Postgres) — další insert dostane max(id)+1
        if target_url.startswith("postgresql"):
            for model in MODELS_IN_ORDER:
                table = model.__tablename__
                s_dst.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                    )
                )
            s_dst.commit()
            print("Sekvence srovnány.")

    print(f"Hotovo, přeneseno {total} řádků.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
