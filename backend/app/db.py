from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def normalize_db_url(url: str) -> str:
    """Doplní SQLAlchemy driver, aby šel vložit i syrový Supabase/Postgres řetězec.

    Supabase dává `postgresql://...` (nebo `postgres://...`); SQLAlchemy potřebuje
    explicitní driver `postgresql+psycopg://...`. SQLite necháme být.
    """
    if url.startswith("postgresql+") or url.startswith("sqlite"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # SQLite + FastAPI threadpool: jedno spojení sdílené mezi vlákny
        return {"connect_args": {"check_same_thread": False}}
    # Postgres / Supabase:
    #  - pool_pre_ping: zahodí odumřelá spojení (důležité přes 24h závodního dne)
    #  - prepare_threshold=None: vypne prepared statements, aby řetězec fungoval
    #    i přes transaction pooler (port 6543); na session pooleru (5432) neškodí
    #  - sslmode=require: Supabase vyžaduje TLS
    return {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "connect_args": {"prepare_threshold": None, "sslmode": "require"},
    }


DATABASE_URL = normalize_db_url(settings.database_url)
engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
