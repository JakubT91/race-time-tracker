"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.requestMagicLink(email.trim());
      setSent(true);
      setDevLink(res.dev_magic_link ?? null);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 460 }}>
      <h1>Race tracker — přihlášení</h1>
      {!sent ? (
        <section className="card">
          <p className="muted" style={{ marginTop: 0 }}>
            Zadej e-mail. Pošleme ti přihlašovací odkaz — žádné heslo.
          </p>
          <form className="inline" onSubmit={submit}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tvuj@email.cz"
              required
              style={{ minWidth: 240 }}
            />
            <button disabled={busy}>{busy ? "Odesílám…" : "Poslat odkaz"}</button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>
      ) : (
        <section className="card">
          <p style={{ marginTop: 0 }}>
            Hotovo. Pokud e-mail existuje, dorazí na <strong>{email}</strong> přihlašovací odkaz. Klikni na něj a budeš
            přihlášený.
          </p>
          {devLink && (
            <p className="muted">
              Vývojový režim (bez e-mailové služby) — přihlas se rovnou: <a href={devLink}>přihlašovací odkaz</a>
            </p>
          )}
        </section>
      )}
    </main>
  );
}
