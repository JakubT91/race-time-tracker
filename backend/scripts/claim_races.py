"""Přiřadí všechny závody bez vlastníka zadanému e-mailu (uživatele vytvoří, když chybí).

Spustit jednou po zavedení účtů, ať dosavadní data patří tobě:
    python scripts/claim_races.py vas@email.cz
"""

import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import engine  # noqa: E402
from app.migrations import run_migrations  # noqa: E402
from app.models import Race, User  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Použití: python scripts/claim_races.py <email>")
        return 1
    email = sys.argv[1].strip().lower()

    run_migrations(engine)
    with Session(engine) as db:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email)
            db.add(user)
            db.commit()
        orphan = db.query(Race).filter(Race.owner_id.is_(None)).all()
        for race in orphan:
            race.owner_id = user.id
        db.commit()
        print(f"Přiřazeno {len(orphan)} závodů uživateli {email} (id {user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
