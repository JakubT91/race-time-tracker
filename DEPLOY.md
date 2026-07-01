# Nasazení aplikace online

Aplikace má tři části: **databáze** (Neon, už hotová), **backend** (FastAPI) a
**frontend** (Next.js). Backend i frontend běží na **Renderu** — obojí je v jednom
`render.yaml`, takže je Blueprint vytvoří společně.

---

## A) Backend → Render (zdarma)

1. Jdi na https://render.com a přihlas se (klidně přes GitHub).
2. Klikni **New** → **Blueprint**.
3. Vyber repozitář **JakubT91/race-time-tracker**. Render najde soubor `render.yaml`
   a nabídne službu `race-tracker-backend`.
4. Klikni **Apply**. Render službu vytvoří, ale počká na tajné proměnné.
5. Ve službě otevři **Environment** a vyplň (hodnoty máš v `backend\.env`):
   - `DATABASE_URL` = tvůj Neon connection string
   - `STRAVA_CLIENT_ID` = 257559
   - `STRAVA_CLIENT_SECRET` = (z `.env`)
   - `FRONTEND_ORIGIN` = zatím nech `http://localhost:3000`, doplníš po nasazení frontendu
   - `PUBLIC_APP_URL` = zatím stejně, doplníš později
   - `BACKEND_BASE_URL` = URL, kterou Render službě přidělí (uvidíš ji nahoře,
     např. `https://race-tracker-backend.onrender.com`) — doplň po prvním buildu
6. Po nasazení ověř `https://<tvuj-backend>.onrender.com/health` → má vrátit `{"status":"ok"}`.

Pozn.: free Render po ~15 min nečinnosti uspí; první požadavek ho probudí (~minuta).
Pro závodní den ho ráno „nakopni" otevřením `/health`, ať běží.

## B) Frontend → Render (součást stejného Blueprintu)

Frontend je v `render.yaml` jako druhá služba `race-tracker-frontend`, takže ho Render
vytvoří spolu s backendem. Po přidání služby (nebo při **Manual sync** blueprintu):
1. Render nabídne novou službu `race-tracker-frontend` — potvrď její vytvoření.
2. Vyplň jedinou proměnnou:
   - `NEXT_PUBLIC_API_URL` = adresa backendu (`https://race-tracker-backend.onrender.com`)
3. Po nasazení dostaneš adresu typu `https://race-tracker-frontend.onrender.com`.

## C) Propojení (důležité)

Po nasazení frontendu se vrať do **backendové** služby na Renderu (Environment) a uprav:
- `FRONTEND_ORIGIN` = adresa frontendu (např. `https://race-tracker-frontend.onrender.com`)
- `PUBLIC_APP_URL` = stejná adresa frontendu

Ve **Strava** nastavení aplikace (https://www.strava.com/settings/api) uprav
**Authorization Callback Domain** na doménu backendu (např. `race-tracker-backend.onrender.com`).

Hotovo — aplikace běží veřejně. Data jsou na Neonu, takže je uvidíš odkudkoli.

## D) Přihlašovací e-maily (magic link) — NUTNÉ pro víc uživatelů

Aby se kamarád (nebo kdokoli) mohl přihlásit svým e-mailem, MUSÍ chodit přihlašovací
odkazy e-mailem. Bez toho se na produkci nikdo nový nepřihlásí. Nastav zdarma Resend:
1. Založ účet na https://resend.com (free tarif stačí).
2. V sekci **API Keys** vytvoř klíč.
3. Na Renderu (Environment) přidej:
   - `RESEND_API_KEY` = ten klíč
   - `MAIL_FROM` = `Race tracker <onboarding@resend.dev>` (testovací odesílatel Resendu;
     pro vlastní doménu ji v Resendu nejdřív ověř)
   - `SECRET_KEY` se vygeneruje automaticky (z `render.yaml`)
   - `DEV_MODE` = `false` se nastaví automaticky (z `render.yaml`)

Bezpečnost: v produkci (`DEV_MODE=false`) se přihlašovací odkaz NIKDY nevrací v aplikaci —
chodí jen e-mailem do dané schránky, takže se nelze přihlásit za cizí e-mail. Vrácení
odkazu rovnou v aplikaci funguje jen lokálně (`DEV_MODE=true`, bez Resendu) pro vývoj.

Pozn.: dosavadní data (bez vlastníka) přiřadíš svému účtu skriptem
`backend/scripts/claim_races.py <tvuj-email>` — pak se přihlásíš tímto e-mailem a uvidíš je.
