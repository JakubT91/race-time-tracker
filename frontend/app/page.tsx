"use client";

import { useCallback, useEffect, useState } from "react";
import AidStationEditor from "@/components/AidStationEditor";
import CheckpointTable from "@/components/CheckpointTable";
import ProfileChart from "@/components/ProfileChart";
import RaceEditForm from "@/components/RaceEditForm";
import RunnerEditForm from "@/components/RunnerEditForm";
import RaceMembersEditor from "@/components/RaceMembersEditor";
import SyncedActivityList from "@/components/SyncedActivityList";
import { api, clearToken, formatDurationLong, getToken, Prediction, Race, RaceProfile, Runner, User, wsUrl } from "@/lib/api";

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [races, setRaces] = useState<Race[]>([]);
  const [race, setRace] = useState<Race | null>(null);
  const [profile, setProfile] = useState<RaceProfile | null>(null);
  const [runners, setRunners] = useState<Runner[]>([]);
  const [runner, setRunner] = useState<Runner | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stravaInfo, setStravaInfo] = useState<string | null>(null);
  const [syncCount, setSyncCount] = useState(0);

  // Přihlašovací brána: bez tokenu na /login, jinak načti uživatele
  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    api
      .me()
      .then((u) => {
        setUser(u);
        setAuthChecked(true);
      })
      .catch(() => {
        // authFetch při 401 sám přesměruje na /login
      });
  }, []);

  // Návrat ze Strava OAuth (?strava=connected/denied/error)
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get("strava");
    if (status === "connected") setStravaInfo("Strava propojena — teď můžeš načíst historii.");
    else if (status) setStravaInfo("Propojení se Stravou se nepovedlo, zkus to znovu.");
    if (status) window.history.replaceState(null, "", "/");
  }, []);

  useEffect(() => {
    if (!authChecked) return;
    api.listRaces().then(setRaces).catch((e) => setError(String(e)));
  }, [authChecked]);

  function logout() {
    clearToken();
    window.location.href = "/login";
  }

  const selectRace = useCallback(async (r: Race) => {
    setRace(r);
    setRunner(null);
    setPrediction(null);
    setProfile(null);
    try {
      setProfile(await api.getProfile(r.id));
    } catch {
      // závod ještě nemá GPX
    }
    setRunners(await api.listRunners(r.id));
  }, []);

  const selectRunner = useCallback(async (rn: Runner) => {
    setRunner(rn);
    setPrediction(null);
    try {
      setPrediction(await api.latestPrediction(rn.id));
    } catch {
      // zatím žádná predikce
    }
  }, []);

  // Živé aktualizace přes WebSocket — po updatu si stáhneme čerstvou predikci
  useEffect(() => {
    if (!runner) return;
    const ws = new WebSocket(wsUrl(runner.id));
    ws.onmessage = () => {
      api.latestPrediction(runner.id).then(setPrediction).catch(() => undefined);
    };
    return () => ws.close();
  }, [runner]);

  async function handleCreateRace(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const start = String(form.get("start") ?? "");
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      let created = await api.createRace(name, start ? new Date(start).toISOString() : null);
      const gpx = form.get("gpx") as File | null;
      if (gpx && gpx.size > 0) created = await api.uploadGpx(created.id, gpx);
      setRaces(await api.listRaces());
      await selectRace(created);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleChangeGpx(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!race || !file) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.uploadGpx(race.id, file);
      setRace(updated);
      setRaces((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setProfile(await api.getProfile(updated.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  function startNewRace() {
    setRace(null);
    setRunner(null);
    setRunners([]);
    setProfile(null);
    setPrediction(null);
  }

  async function handleCreateRunner(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!race) return;
    const form = new FormData(e.currentTarget);
    const hours = Number(form.get("hours") ?? 0);
    const minutes = Number(form.get("minutes") ?? 0);
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRunner(race.id, {
        name: String(form.get("name") ?? ""),
        target_time_s: hours * 3600 + minutes * 60,
        feel: Number(form.get("feel") ?? 3),
        livetrack_url: String(form.get("livetrack") ?? "").trim() || null,
      });
      setRunners(await api.listRunners(race.id));
      await selectRunner(created);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSyncHistory() {
    if (!runner) return;
    setBusy(true);
    setError(null);
    setStravaInfo("Stahuji historii ze Stravy, může to trvat i minutu…");
    try {
      const result = await api.syncStravaHistory(runner.id);
      const c = result.calibration;
      const parts = [`${result.activities_used} aktivit`];
      if (c.gap_uphill_scale) parts.push(`kopce ×${c.gap_uphill_scale.toFixed(2)}`);
      if (c.fatigue_k) parts.push(`únava ${(c.fatigue_k * 100).toFixed(0)} %`);
      setStravaInfo(`Kalibrace hotová (${parts.join(", ")}). Spusť novou predikci.`);
      setSyncCount((n) => n + 1);
    } catch (err) {
      setStravaInfo(null);
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleConnectStrava() {
    if (!runner) return;
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await api.connectStrava(runner.id);
      window.location.href = authorize_url;
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  async function handlePredict() {
    if (!runner) return;
    setBusy(true);
    setError(null);
    try {
      setPrediction(await api.predict(runner.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!authChecked) {
    return (
      <main>
        <p className="muted">Načítám…</p>
      </main>
    );
  }

  return (
    <main>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ margin: 0 }}>Race time tracker</h1>
        <span className="muted">
          {user?.email}{" "}
          {user?.is_admin && (
            <a href="/admin" style={{ marginLeft: 8 }}>
              Admin
            </a>
          )}
          <button type="button" onClick={logout} style={{ background: "#5f5e5a", marginLeft: 8 }}>
            Odhlásit
          </button>
        </span>
      </div>
      {error && <p className="error">{error}</p>}

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Závod</h2>
        {!race ? (
          <>
            {races.length > 0 && (
              <p>
                <select
                  value=""
                  onChange={(e) => {
                    const found = races.find((r) => r.id === Number(e.target.value));
                    if (found) void selectRace(found);
                  }}
                >
                  <option value="">— vyber existující závod —</option>
                  {races.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </p>
            )}
            <form className="inline" onSubmit={handleCreateRace}>
              <input name="name" placeholder="Název závodu" required />
              <input name="start" type="datetime-local" title="Start závodu" />
              <input name="gpx" type="file" accept=".gpx" />
              <button disabled={busy}>Založit závod</button>
            </form>
          </>
        ) : (
          <>
            <p style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <select
                value={race.id}
                onChange={(e) => {
                  const found = races.find((r) => r.id === Number(e.target.value));
                  if (found) void selectRace(found);
                }}
              >
                {races.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <button type="button" onClick={startNewRace} style={{ background: "#5f5e5a" }}>
                + Nový závod
              </button>
            </p>
            <p className="muted" style={{ marginBottom: 4 }}>
              {race.name}
              {race.total_distance_m
                ? ` · ${(race.total_distance_m / 1000).toFixed(1)} km · ${Math.round(race.total_ascent_m ?? 0)} m převýšení`
                : " · zatím bez GPX trasy"}
            </p>
            <RaceEditForm
              race={race}
              onSaved={(updated) => {
                setRace(updated);
                setRaces((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
              }}
            />
            <p className="muted" style={{ marginBottom: 4 }}>
              {race.total_distance_m ? "Změnit trasu (nahrát nové GPX):" : "Nahrát GPX trasu:"}
            </p>
            <input type="file" accept=".gpx" onChange={handleChangeGpx} disabled={busy} />
            <AidStationEditor raceId={race.id} onSaved={() => undefined} />
            {user && race.owner_id === user.id && <RaceMembersEditor raceId={race.id} />}
          </>
        )}
      </section>

      {race && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Běžec</h2>
          {runners.length > 0 && (
            <p>
              <select
                value={runner?.id ?? ""}
                onChange={(e) => {
                  const found = runners.find((r) => r.id === Number(e.target.value));
                  if (found) void selectRunner(found);
                }}
              >
                <option value="">— vyber běžce —</option>
                {runners.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </p>
          )}
          <form className="inline" onSubmit={handleCreateRunner}>
            <input name="name" placeholder="Jméno" required />
            <input name="hours" type="number" min={0} max={99} placeholder="hod" style={{ width: 70 }} required />
            <input name="minutes" type="number" min={0} max={59} placeholder="min" style={{ width: 70 }} required />
            <select name="feel" defaultValue="3" title="Subjektivní pocit (1 = skvělý, 5 = špatný)">
              <option value="1">Pocit: skvělý</option>
              <option value="2">Pocit: dobrý</option>
              <option value="3">Pocit: normální</option>
              <option value="4">Pocit: slabší</option>
              <option value="5">Pocit: špatný</option>
            </select>
            <input name="livetrack" placeholder="Garmin LiveTrack URL (volitelné)" style={{ minWidth: 260 }} />
            <button disabled={busy}>Přidat běžce</button>
          </form>
          {runner && (
            <p style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button onClick={handlePredict} disabled={busy}>
                {busy ? "Počítám…" : "Spustit predikci"}
              </button>
              <button type="button" style={{ background: "#fc4c02" }} disabled={busy} onClick={handleConnectStrava}>
                Propojit se Stravou
              </button>
              <button type="button" onClick={handleSyncHistory} disabled={busy}>
                Načíst historii ze Stravy
              </button>
            </p>
          )}
          {stravaInfo && <p className="muted">{stravaInfo}</p>}
          {runner && <SyncedActivityList runnerId={runner.id} refreshKey={syncCount} />}
          {runner && (
            <RunnerEditForm
              runner={runner}
              onSaved={(updated) => {
                setRunner(updated);
                setRunners((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
              }}
            />
          )}
        </section>
      )}

      {profile && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Profil trasy a predikované časy</h2>
          <ProfileChart profile={profile} prediction={prediction} />
          <p className="muted">
            Šedá plocha = výškový profil. Fialová čára = medián času průchodu, fialový pás = rozptyl P10–P90.
            Zelené čáry = občerstvovačky, oranžová = aktuální poloha běžce.
          </p>
        </section>
      )}

      {prediction && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>
            Cíl: {formatDurationLong(prediction.finish.p50)}{" "}
            <span className="muted">
              ({formatDurationLong(prediction.finish.p10)} – {formatDurationLong(prediction.finish.p90)}, 80% interval)
            </span>
          </h2>
          <CheckpointTable prediction={prediction} raceStart={race?.start_time ?? null} />
        </section>
      )}
    </main>
  );
}
