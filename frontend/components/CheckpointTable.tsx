"use client";

import { formatDurationLong, Prediction } from "@/lib/api";

function clock(raceStartIso: string | null, offsetS: number): string {
  if (!raceStartIso) return formatDurationLong(offsetS);
  const t = new Date(new Date(raceStartIso).getTime() + offsetS * 1000);
  return t.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
}

export default function CheckpointTable({
  prediction,
  raceStart,
}: {
  prediction: Prediction;
  raceStart: string | null;
}) {
  const rows = [
    ...prediction.aid_stations.map((a) => ({
      label: a.name,
      km: a.distance_m / 1000,
      p10: a.p10,
      p50: a.p50,
      p90: a.p90,
    })),
    {
      label: "Cíl",
      km: prediction.per_km.length ? prediction.per_km[prediction.per_km.length - 1].km : 0,
      ...prediction.finish,
    },
  ].sort((a, b) => a.km - b.km);

  return (
    <table className="checkpoints">
      <thead>
        <tr>
          <th>Místo</th>
          <th>km</th>
          <th>Příchod (medián)</th>
          <th>Rozptyl P10–P90</th>
          <th>Čas závodu</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.label}-${r.km}`}>
            <td>{r.label}</td>
            <td>{r.km.toFixed(1)}</td>
            <td>{clock(raceStart, r.p50)}</td>
            <td>
              {clock(raceStart, r.p10)} – {clock(raceStart, r.p90)}
            </td>
            <td>{formatDurationLong(r.p50)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
