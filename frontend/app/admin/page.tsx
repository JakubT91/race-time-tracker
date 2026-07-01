"use client";

import { useEffect, useState } from "react";
import { AdminRace, AdminStats, AdminUser, api, getToken } from "@/lib/api";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("cs-CZ", { dateStyle: "short", timeStyle: "short" });
}

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [races, setRaces] = useState<AdminRace[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    Promise.all([api.adminStats(), api.adminUsers(), api.adminRaces()])
      .then(([s, u, r]) => {
        setStats(s);
        setUsers(u);
        setRaces(r);
      })
      .catch((e) => {
        if (String(e).includes("403")) setError("Tahle sekce je jen pro administrátora.");
        else setError(String(e));
      });
  }, []);

  return (
    <main>
      <p style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <a href="/">← zpět do aplikace</a>
      </p>
      <h1>Administrace</h1>
      {error && <p className="error">{error}</p>}

      {stats && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Přehled</h2>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div><strong style={{ fontSize: 24 }}>{stats.users}</strong><div className="muted">uživatelů</div></div>
            <div><strong style={{ fontSize: 24 }}>{stats.races}</strong><div className="muted">závodů</div></div>
            <div><strong style={{ fontSize: 24 }}>{stats.runners}</strong><div className="muted">běžců</div></div>
            <div><strong style={{ fontSize: 24 }}>{stats.predictions}</strong><div className="muted">predikcí</div></div>
          </div>
        </section>
      )}

      {users.length > 0 && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Uživatelé ({users.length})</h2>
          <table className="checkpoints">
            <thead>
              <tr>
                <th>E-mail</th>
                <th>Registrace</th>
                <th>Poslední přihlášení</th>
                <th>Závody</th>
                <th>Sdílené</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{fmtDate(u.created_at)}</td>
                  <td>{fmtDate(u.last_login_at)}</td>
                  <td>{u.races_owned}</td>
                  <td>{u.memberships}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {races.length > 0 && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Závody ({races.length})</h2>
          <table className="checkpoints">
            <thead>
              <tr>
                <th>Název</th>
                <th>Vlastník</th>
                <th>Start</th>
                <th>km</th>
                <th>Běžci</th>
                <th>Občerstvovačky</th>
              </tr>
            </thead>
            <tbody>
              {races.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.owner_email ?? "—"}</td>
                  <td>{fmtDate(r.start_time)}</td>
                  <td>{r.total_distance_m ? (r.total_distance_m / 1000).toFixed(1) : "—"}</td>
                  <td>{r.runners}</td>
                  <td>{r.aid_stations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
