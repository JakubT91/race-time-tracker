# Vítej v Race trackeru 🏃‍♂️⏱️

Aplikace, která **předpovídá, v jakém čase bude běžec na trase** — aby jeho support tým
věděl, kdy ho čekat na kterém místě (občerstvovačky, checkpointy, cíl).

**Aplikace:** https://race-tracker-frontend.onrender.com

## Co aplikace umí

- Z **GPX trasy** spočítá výškový profil a rozdělí ji na úseky.
- Pomocí simulace odhadne **čas průchodu každým kilometrem** — v rozptylu (od–do), ne jen jedno číslo.
- Zohlední **převýšení a sklon, postupnou únavu, počasí (déšť/teplo/sníh), běh za tmy
  a zastávky na občerstvovačkách**.
- Umí načíst **historii běžce ze Stravy** a přizpůsobit predikci jeho reálné formě.
- Za závodu sleduje **živou polohu z Garmin LiveTracku** a průběžně predikci zpřesňuje.
- Výstup: **graf trasy s časy** a **tabulka příchodů** na jednotlivá místa.

## Jak počítá čas — co všechno zohledňuje

Trasu rozdělí na úseky po ~100 m a pro každý zná sklon i nadmořskou výšku. Pak počítá:

- **Převýšení a sklon:** čím prudší do kopce, tím víc zpomalí (podle energetické
  náročnosti běhu — strmější = „dražší"). I prudký sběh zpomaluje (brzdění, technika).
- **Postupná únava:** tempo se s přibývajícími kilometry zhoršuje — u ultra klidně
  o desítky procent v druhé půlce. Míru „vyhoření" se učí z historie a za závodu ji upřesňuje.
- **Počasí:** pro každý úsek se podívá na předpověď (Open-Meteo) v čase, kdy tam běžec
  podle výpočtu bude — horko nad ~15 °C zpomaluje, déšť a bláto víc, sníh nejvíc,
  mlha (špatná viditelnost) taky.
- **Tma:** ze zeměpisné polohy a času spočítá východ a západ slunce, a tím které úseky
  připadnou na noc — v noci (hlavně na technickém terénu) se běží pomaleji.
- **Občerstvovačky:** přičte plánované zastávky, s trochou nejistoty (někdy se zdržíš víc).
- **Rozptyl místo jednoho čísla:** spustí tisíce „co kdyby" simulací (tempo, únava,
  počasí a zastávky se pokaždé lehce liší) a z nich udělá interval — proto vidíš čas
  „od–do", ne jen jedno číslo, a spolu s tím i jak moc si je jistý.
- **Za závodu (živě):** z Garmin LiveTracku bere reálnou polohu, tempo, tep a kadenci,
  porovná je s odhadem a predikci průběžně koriguje. Rostoucí tep při stejném tempu =
  nastupující únava → model zareaguje dřív. Čím dál v závodě, tím užší (jistější) rozptyl.
- **Osobní kalibrace ze Stravy:** z historie zjistí, jak konkrétně tenhle běžec zpomaluje
  do kopce a jak mu klesá tempo na dlouhých bězích — predikce pak není „průměrný běžec", ale on sám.

## Jak se přihlásit (bez hesla)

1. Otevři **https://race-tracker-frontend.onrender.com**
   *(první načtení může trvat ~1 min, než se web probudí)*
2. Zadej svůj **e-mail** → **Poslat odkaz**.
3. Přijde ti e-mail „Přihlášení do Race tracker" — klikni na odkaz. A jsi uvnitř.

Přístup má jen povolený seznam e-mailů. Když se nedostaneš dovnitř, napiš správci, ať tě přidá.

## Jak to použít

1. **+ Nový závod** → název, datum a čas startu, nahraj **GPX** trasy.
2. **Občerstvovačky** → název · kilometr · minuty zastávky → ulož.
3. **Běžec** → jméno, cílový čas, jak se cítí (1–5) a v den závodu jeho **Garmin LiveTrack** odkaz.
4. **Propojit se Stravou → Načíst historii** *(volitelné, ale zpřesní predikci)*.
5. **Spustit predikci** → graf trasy s časy + tabulka příchodů.

## Sdílení s týmem

Každý vidí jen svoje závody. Vlastník závodu může přes e-mail **pozvat** další lidi
ze support týmu — ti pak uvidí tentýž závod a běžce.

## Pod kapotou (pro zvědavé) — technologický stack

- **Frontend:** Next.js (React, TypeScript), grafy Recharts
- **Backend:** Python + FastAPI; predikce = Monte Carlo simulace (Minetti GAP model
  pro sklon, únavový model, počasí z Open-Meteo, výpočet tmy přes `astral`)
- **Data běžce:** Garmin LiveTrack (živá poloha za závodu), Strava API (historie a osobní kalibrace)
- **Databáze:** PostgreSQL (Neon, cloud)
- **Přihlášení:** magic link (bez hesla), JWT session, e-maily přes Gmail SMTP
- **Hosting:** Render (backend + frontend), Neon (databáze) — vše běží v cloudu 24/7
- **Kód:** https://github.com/JakubT91/race-time-tracker (privátní)
