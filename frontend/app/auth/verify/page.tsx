"use client";

import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

export default function VerifyPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setError("Chybí token v odkazu.");
      return;
    }
    api
      .verifyMagicLink(token)
      .then((res) => {
        setToken(res.access_token);
        window.location.href = "/";
      })
      .catch(() => setError("Odkaz je neplatný nebo vypršel. Vyžádej si nový na přihlašovací stránce."));
  }, []);

  return (
    <main style={{ maxWidth: 460 }}>
      <h1>Přihlašování…</h1>
      {error ? (
        <section className="card">
          <p className="error" style={{ marginTop: 0 }}>
            {error}
          </p>
          <p>
            <a href="/login">Zpět na přihlášení</a>
          </p>
        </section>
      ) : (
        <p className="muted">Ověřuji odkaz, počkej chvíli…</p>
      )}
    </main>
  );
}
