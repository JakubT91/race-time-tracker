"use client";

import { useEffect, useState } from "react";
import { AidStation, api } from "@/lib/api";

interface Row {
  name: string;
  km: string;
  minutes: string;
}

function toRows(stations: AidStation[]): Row[] {
  return stations.map((s) => ({
    name: s.name,
    km: (s.distance_m / 1000).toString(),
    minutes: (s.expected_stop_s / 60).toString(),
  }));
}

export default function AidStationEditor({ raceId, onSaved }: { raceId: number; onSaved: () => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setMessage(null);
    api
      .listAidStations(raceId)
      .then((stations) => setRows(toRows(stations)))
      .catch(() => setRows([]));
  }, [raceId]);

  function update(index: number, field: keyof Row, value: string) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const stations = rows
        .filter((r) => r.name.trim() && Number(r.km) > 0)
        .map((r) => ({
          name: r.name.trim(),
          distance_m: Number(r.km) * 1000,
          expected_stop_s: Math.max(Number(r.minutes) || 0, 0) * 60,
        }))
        .sort((a, b) => a.distance_m - b.distance_m);
      const saved = await api.setAidStations(raceId, stations);
      setRows(toRows(saved));
      setMessage(`Uloženo ${saved.length} občerstvovaček. Spusť novou predikci, ať se propíšou do časů.`);
      onSaved();
    } catch (err) {
      setMessage(`Uložení selhalo: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 16 }}>Občerstvovačky</h2>
      {rows.map((row, i) => (
        <div className="inline" style={{ display: "flex", gap: 8, marginBottom: 6 }} key={i}>
          <input
            value={row.name}
            onChange={(e) => update(i, "name", e.target.value)}
            placeholder="Název (např. AS1 Pec)"
          />
          <input
            value={row.km}
            onChange={(e) => update(i, "km", e.target.value)}
            type="number"
            min={0}
            step="0.1"
            placeholder="km"
            style={{ width: 90 }}
            title="Kilometr trasy"
          />
          <input
            value={row.minutes}
            onChange={(e) => update(i, "minutes", e.target.value)}
            type="number"
            min={0}
            step="0.5"
            placeholder="min"
            style={{ width: 90 }}
            title="Očekávaná zastávka v minutách"
          />
          <button type="button" onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))} style={{ background: "#a32d2d" }}>
            ×
          </button>
        </div>
      ))}
      <p style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={() => setRows((prev) => [...prev, { name: `AS${prev.length + 1}`, km: "", minutes: "3" }])}>
          Přidat občerstvovačku
        </button>
        <button type="button" onClick={save} disabled={busy}>
          Uložit občerstvovačky
        </button>
      </p>
      <p className="muted">Název · kilometr trasy · plánovaná zastávka v minutách.</p>
      {message && <p className="muted">{message}</p>}
    </div>
  );
}
