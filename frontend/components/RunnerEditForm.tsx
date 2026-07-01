"use client";

import { useEffect, useState } from "react";
import { Runner, api } from "@/lib/api";

export default function RunnerEditForm({ runner, onSaved }: { runner: Runner; onSaved: (r: Runner) => void }) {
  const [hours, setHours] = useState("");
  const [minutes, setMinutes] = useState("");
  const [feel, setFeel] = useState("3");
  const [livetrack, setLivetrack] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setHours(Math.floor(runner.target_time_s / 3600).toString());
    setMinutes(Math.floor((runner.target_time_s % 3600) / 60).toString());
    setFeel(runner.feel.toString());
    setLivetrack(runner.livetrack_url ?? "");
    setMessage(null);
  }, [runner]);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await api.updateRunner(runner.id, {
        target_time_s: Number(hours) * 3600 + Number(minutes) * 60,
        feel: Number(feel),
        livetrack_url: livetrack.trim() || null,
      });
      onSaved(updated);
      setMessage("Uloženo. Spusť novou predikci, ať se změny propíšou.");
    } catch (err) {
      setMessage(`Uložení selhalo: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eceae2" }}>
      <p className="muted" style={{ marginTop: 0 }}>
        Úprava běžce {runner.name} — cílový čas, pocit a LiveTrack odkaz (ten vlož v den závodu):
      </p>
      <div className="inline" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input value={hours} onChange={(e) => setHours(e.target.value)} type="number" min={0} max={99} style={{ width: 70 }} title="Cílový čas — hodiny" />
        <input value={minutes} onChange={(e) => setMinutes(e.target.value)} type="number" min={0} max={59} style={{ width: 70 }} title="Cílový čas — minuty" />
        <select value={feel} onChange={(e) => setFeel(e.target.value)} title="Subjektivní pocit">
          <option value="1">Pocit: skvělý</option>
          <option value="2">Pocit: dobrý</option>
          <option value="3">Pocit: normální</option>
          <option value="4">Pocit: slabší</option>
          <option value="5">Pocit: špatný</option>
        </select>
        <input
          value={livetrack}
          onChange={(e) => setLivetrack(e.target.value)}
          placeholder="Garmin LiveTrack URL"
          style={{ minWidth: 280 }}
        />
        <button type="button" onClick={save} disabled={busy}>
          Uložit změny
        </button>
      </div>
      {message && <p className="muted">{message}</p>}
    </div>
  );
}
