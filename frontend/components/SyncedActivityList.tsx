"use client";

import { useEffect, useState } from "react";
import { SyncedActivity, api } from "@/lib/api";

export default function SyncedActivityList({ runnerId, refreshKey }: { runnerId: number; refreshKey: number }) {
  const [activities, setActivities] = useState<SyncedActivity[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api
      .listSyncedActivities(runnerId)
      .then(setActivities)
      .catch(() => setActivities([]));
  }, [runnerId, refreshKey]);

  if (activities.length === 0) return null;

  const used = activities.filter((a) => a.used_for_calibration);

  return (
    <div style={{ marginTop: 12 }}>
      <button type="button" onClick={() => setOpen(!open)} style={{ background: "#5f5e5a" }}>
        {open ? "Skrýt běhy ze Stravy" : `Běhy ze Stravy (${used.length} v kalibraci z ${activities.length} nalezených)`}
      </button>
      {open && (
        <table className="checkpoints" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Název</th>
              <th>km</th>
              <th>Převýšení</th>
              <th>Čas</th>
              <th>V kalibraci</th>
            </tr>
          </thead>
          <tbody>
            {activities.map((a) => (
              <tr key={a.strava_id} style={a.used_for_calibration ? {} : { opacity: 0.55 }}>
                <td>{new Date(a.start_date).toLocaleDateString("cs-CZ")}</td>
                <td>
                  <a href={`https://www.strava.com/activities/${a.strava_id}`} target="_blank" rel="noreferrer">
                    {a.name || "(bez názvu)"}
                  </a>
                </td>
                <td>{(a.distance_m / 1000).toFixed(1)}</td>
                <td>{Math.round(a.elevation_gain_m)} m</td>
                <td>
                  {Math.floor(a.moving_time_s / 3600)}:{String(Math.floor((a.moving_time_s % 3600) / 60)).padStart(2, "0")}
                </td>
                <td>{a.used_for_calibration ? "ano" : "ne"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
