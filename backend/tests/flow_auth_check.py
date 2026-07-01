"""Izolovaná kontrola přihlášení + práv (dočasná SQLite, nezávisle na Neonu).

Spouští se jako skript:  python tests/flow_auth_check.py
"""

import os
import sys
from pathlib import Path

# Env MUSÍ být nastavené před importem app (config se čte při importu)
_TMP = Path(__file__).resolve().parent / "_authtest.db"
if _TMP.exists():
    _TMP.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["RESEND_API_KEY"] = ""  # bez e-mailu -> dev_magic_link v odpovědi
os.environ["ADMIN_EMAILS"] = "alice@example.com"  # alice je admin, bob ne
os.environ["ALLOWED_EMAILS"] = "alice@example.com,bob@example.com"  # carol NENÍ na allowlistu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402

main.start_scheduler = lambda: None  # v testu nechceme poller
main.stop_scheduler = lambda: None


def login(client: TestClient, email: str) -> str:
    r = client.post("/auth/request", json={"email": email})
    assert r.status_code == 200, r.text
    link = r.json()["dev_magic_link"]
    token = link.split("token=")[1]
    r = client.post("/auth/verify", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def main_check() -> int:
    with TestClient(main.app) as c:
        # Bez přihlášení = 401
        assert c.get("/races").status_code == 401

        alice = login(c, "alice@example.com")
        bob = login(c, "bob@example.com")

        # Alice založí závod
        r = c.post("/races", json={"name": "Alpine"}, headers=h(alice))
        assert r.status_code == 200, r.text
        race_id = r.json()["id"]

        # Alice ho vidí, Bob ne
        assert [x["id"] for x in c.get("/races", headers=h(alice)).json()] == [race_id]
        assert c.get("/races", headers=h(bob)).json() == []
        assert c.get(f"/races/{race_id}/aid-stations", headers=h(bob)).status_code == 403

        # Bob nemůže smazat (není vlastník ani člen)
        assert c.delete(f"/races/{race_id}", headers=h(bob)).status_code == 403

        # Alice pozve Boba -> Bob teď vidí a má přístup
        r = c.post(f"/races/{race_id}/members", json={"email": "bob@example.com"}, headers=h(alice))
        assert r.status_code == 200, r.text
        assert [x["id"] for x in c.get("/races", headers=h(bob)).json()] == [race_id]
        assert c.get(f"/races/{race_id}/aid-stations", headers=h(bob)).status_code == 200

        # Bob (člen) může upravit obsah, ale NE smazat (jen vlastník)
        assert c.patch(f"/races/{race_id}", json={"name": "Alpine 2"}, headers=h(bob)).status_code == 200
        assert c.delete(f"/races/{race_id}", headers=h(bob)).status_code == 403

        # Členy vidí oba; vlastník je owner
        members = c.get(f"/races/{race_id}/members", headers=h(alice)).json()
        roles = {m["email"]: m["role"] for m in members}
        assert roles == {"alice@example.com": "owner", "bob@example.com": "member"}, roles

        # Pozvání dává přístup i mimo allowlist:
        # carol není povolená -> nesmí se přihlásit
        assert c.post("/auth/request", json={"email": "carol@example.com"}).status_code == 403
        # alice ji pozve k závodu -> teď se smí přihlásit a vidí ho
        assert c.post(f"/races/{race_id}/members", json={"email": "carol@example.com"}, headers=h(alice)).status_code == 200
        carol = login(c, "carol@example.com")
        assert [x["id"] for x in c.get("/races", headers=h(carol)).json()] == [race_id]

        # Alice (vlastník) smaže
        assert c.delete(f"/races/{race_id}", headers=h(alice)).status_code == 204
        assert c.get("/races", headers=h(alice)).json() == []

        # Neplatný token = 401
        assert c.get("/races", headers=h("nesmysl")).status_code == 401

        # Admin sekce: alice (admin) ano, bob (ne) 403
        assert c.get("/auth/me", headers=h(alice)).json()["is_admin"] is True
        assert c.get("/auth/me", headers=h(bob)).json()["is_admin"] is False
        assert c.get("/admin/stats", headers=h(alice)).status_code == 200
        assert c.get("/admin/users", headers=h(alice)).status_code == 200
        assert c.get("/admin/stats", headers=h(bob)).status_code == 403
        assert c.get("/admin/users", headers=h(bob)).status_code == 403

    print("FLOW AUTH CHECK OK")
    return 0


if __name__ == "__main__":
    code = main_check()
    try:
        import app.db

        app.db.engine.dispose()
        if _TMP.exists():
            _TMP.unlink()
    except (OSError, PermissionError):
        pass
    raise SystemExit(code)
