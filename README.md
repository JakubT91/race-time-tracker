# Race time tracker

Predikce času doběhu na konkrétní trase pro support tým běžce.

## Živá aplikace

Nasazená a dostupná online:

- **Aplikace:** https://race-tracker-frontend.onrender.com
- **API:** https://race-tracker-backend.onrender.com

Přihlášení je bez hesla (magic link na e-mail). Návod pro uživatele: [NAVOD.md](NAVOD.md),
uvítací přehled: [ONBOARDING.md](ONBOARDING.md).

**Nasazení:** frontend + backend na [Render](https://render.com) (jeden `render.yaml`,
free plan), databáze na [Neon](https://neon.tech) (cloud Postgres). Postup a proměnné
viz [DEPLOY.md](DEPLOY.md). Push do `main` → automatické nasazení.

## Technologický stack

- **Frontend:** Next.js (React, TypeScript), grafy Recharts
- **Backend:** Python + FastAPI; predikce = Monte Carlo simulace (Minetti GAP model, únava, počasí Open-Meteo, tma `astral`)
- **Data běžce:** Garmin LiveTrack (živá poloha), Strava API (historie + osobní kalibrace)
- **Databáze:** PostgreSQL (Neon)
- **Auth:** magic link (bez hesla), JWT session, e-maily přes Gmail SMTP; přístup přes allowlist, admin sekce
- **Hosting:** Render (backend + frontend), Neon (DB)

## Struktura

- `backend/` — FastAPI + predikční engine (Monte Carlo simulace), polling Garmin LiveTrack, Open-Meteo počasí, auth/allowlist/admin
- `frontend/` — Next.js, výškový profil trasy s vyznačenými predikovanými časy (P10/P50/P90) a tabulka checkpointů
- `docker-compose.yml` — PostgreSQL + Redis + backend + frontend (lokální varianta)

## Rychlý start (vývoj, bez Dockeru)

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

Bez `DATABASE_URL` se použije lokální SQLite (`backend/tracking.db`) — pro vývoj není potřeba nic dalšího.

Frontend (Node 20+):

```powershell
cd frontend
npm install
npm run dev
```

Aplikace běží na http://localhost:3000, API na http://localhost:8000 (OpenAPI docs: http://localhost:8000/docs).

## Typický workflow (API)

Všechny endpointy (kromě `/auth/*` a `/health`) vyžadují přihlášení — hlavička
`Authorization: Bearer <token>` z `/auth/verify`. Závod vidí jen jeho vlastník nebo
pozvaný člen (`/races/{id}/members`).

1. `POST /races` — založení závodu (název, datum startu)
2. `POST /races/{id}/gpx` — upload GPX (multipart) → segmentace trasy po 100 m, vyhlazení výškového profilu
3. `POST /races/{id}/aid-stations` — občerstvovačky (km + očekávaná délka zastávky)
4. `POST /races/{id}/runners` — běžec: cílový čas, subjektivní pocit (1–5), Garmin LiveTrack URL
5. `POST /runners/{id}/predict` — spuštění Monte Carlo simulace → časy průchodu po km s percentily
6. Scheduler každých 30 s polluje LiveTrack, ukládá trackpointy (vč. tepu a kadence pro model),
   rekalibruje parametry běžce a přepočítává predikci; frontend dostává update přes WebSocket.

## Spuštění přes Docker

```powershell
docker compose up --build
```

## Testy

```powershell
cd backend
pytest
```

## Konfigurace

Viz `backend/.env.example`. Klíčové proměnné: `DATABASE_URL`, `REDIS_URL`, `STRAVA_CLIENT_ID/SECRET`
(historie běžce pro osobní kalibraci — volitelné).
