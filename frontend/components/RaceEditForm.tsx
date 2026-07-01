"use client";

import { useEffect, useState } from "react";
import { Race, api } from "@/lib/api";

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function RaceEditForm({ race, onSaved }: { race: Race; onSaved: (r: Race) => void }) {
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Záměrně závisí jen na race.id — jinak by uložení (které nahradí objekt race)
  // okamžitě smazalo potvrzovací hlášku.
  useEffect(() => {
    setName(race.name);
    setStart(toLocalInput(race.start_time));
    setMessage(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [race.id]);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await api.updateRace(race.id, {
        name: name.trim() || undefined,
        start_time: start ? new Date(start).toISOString() : null,
      });
      onSaved(updated);
      setMessage("Uloženo. Spusť novou predikci, ať se nový čas startu propíše do časů příchodu.");
    } catch (err) {
      setMessage(`Uložení selhalo: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eceae2" }}>
      <p className="muted" style={{ marginTop: 0 }}>
        Úprava závodu — název a čas startu:
      </p>
      <div className="inline" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Název závodu" />
        <input value={start} onChange={(e) => setStart(e.target.value)} type="datetime-local" title="Čas startu" />
        <button type="button" onClick={save} disabled={busy}>
          Uložit závod
        </button>
      </div>
      {message && <p className="muted">{message}</p>}
    </div>
  );
}
