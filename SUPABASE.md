# Přechod na Supabase (cloudová databáze)

Aplikace běží stejně jako dosud — jen místo lokálního souboru `tracking.db` ukládá data
do Postgres databáze v cloudu. Výhoda: data jsou dostupná i z jiného počítače a nezáleží
na jednom souboru. Backend pořád musí běžet (Supabase je jen databáze, ne hosting aplikace).

## 1. Založ projekt na Supabase

1. Jdi na https://supabase.com, přihlas se (klidně přes GitHub) a klikni **New project**.
2. Zadej název, vyber region co nejblíž (např. **Frankfurt / eu-central**) a nech si
   vygenerovat **databázové heslo** — ulož si ho, budeš ho potřebovat.
3. Počkej ~2 minuty, než se projekt vytvoří.

## 2. Zkopíruj connection string (Session pooler)

1. V projektu klikni nahoře na tlačítko **Connect**.
2. V sekci **Connection string** vyber **Session pooler** (port 5432).
   - Je to volba vhodná pro stále běžící backend a funguje i bez IPv6.
3. Zkopíruj řetězec. Vypadá takhle:
   ```
   postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```
4. `[YOUR-PASSWORD]` nahraď heslem z kroku 1.

## 3. Vlož ho do konfigurace

Otevři `backend\.env` a přidej řádek (heslo už dosazené):

```
DATABASE_URL=postgresql://postgres.abcdefgh:tvojeHeslo@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

Driver se doplní automaticky, syrový řetězec ze Supabase stačí. `STRAVA_*` řádky nech být.

## 4. Doinstaluj Postgres ovladač

V adresáři `backend` (s aktivním `.venv`):

```powershell
.venv\Scripts\python.exe -m pip install -e .[postgres]
```

## 5. Přenes stávající data (volitelné)

Pokud chceš do Supabase dostat své dosavadní závody a běžce z lokální databáze:

```powershell
.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py "VLOŽ_SEM_CONNECTION_STRING"
```

(Connection string dej do uvozovek.) Skript lze spustit i opakovaně — data se nezduplikují.
Pokud ti stačí začít načisto, tenhle krok přeskoč — tabulky se v Supabase vytvoří samy
při prvním spuštění backendu.

## 6. Spusť aplikaci jako obvykle

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Backend se teď připojuje k Supabase. V Supabase dashboardu pod **Table Editor** uvidíš
tabulky (races, runners, …) a v nich svá data.

## Zpět na lokální SQLite

Stačí v `backend\.env` smazat (nebo zakomentovat `#`) řádek `DATABASE_URL` a restartovat
backend — vrátí se k souboru `tracking.db`.

## Časté potíže

- **„password authentication failed"** — špatné heslo v connection stringu (to z kroku 1,
  ne heslo k účtu Supabase).
- **Connection/timeout** — ověř, že jsi vzal **Session pooler** (port 5432), ne Direct
  connection. Pooler funguje i bez IPv6.
- **Data nikde** — zkontroluj, že `DATABASE_URL` v `.env` je správně a backend jsi po
  změně restartoval.
