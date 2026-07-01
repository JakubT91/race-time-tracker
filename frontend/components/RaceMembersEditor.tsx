"use client";

import { useEffect, useState } from "react";
import { Member, api } from "@/lib/api";

export default function RaceMembersEditor({ raceId }: { raceId: number }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [inviteLink, setInviteLink] = useState<{ email: string; link: string } | null>(null);
  const [copied, setCopied] = useState(false);

  function reload() {
    api
      .listMembers(raceId)
      .then(setMembers)
      .catch(() => setMembers([]));
  }

  useEffect(() => {
    reload();
    setMessage(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raceId]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    setCopied(false);
    try {
      const invited = email.trim();
      const m = await api.inviteMember(raceId, invited);
      setEmail("");
      setMessage("Pozváno. E-mail se pokusil odeslat — ale nejjistější je poslat kamarádovi tento odkaz sám (WhatsApp, Messenger…):");
      setInviteLink(m.login_link ? { email: invited, link: m.login_link } : null);
      reload();
    } catch (err) {
      setMessage(`Pozvání selhalo: ${String(err)}`);
      setInviteLink(null);
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink.link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  async function remove(userId: number) {
    setBusy(true);
    try {
      await api.removeMember(raceId, userId);
      reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eceae2" }}>
      <p className="muted" style={{ marginTop: 0 }}>
        Sdílení závodu — pozvi support tým e-mailem, uvidí závod i běžce:
      </p>
      <form className="inline" onSubmit={invite} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@kolegy.cz" style={{ minWidth: 220 }} required />
        <button disabled={busy}>Pozvat</button>
      </form>
      <table className="checkpoints" style={{ marginTop: 8 }}>
        <tbody>
          {members.map((m) => (
            <tr key={m.user_id}>
              <td>{m.email}</td>
              <td>{m.role === "owner" ? "vlastník" : "člen"}</td>
              <td style={{ textAlign: "right" }}>
                {m.role === "member" && (
                  <button type="button" onClick={() => remove(m.user_id)} disabled={busy} style={{ background: "#a32d2d" }}>
                    odebrat
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {message && <p className="muted">{message}</p>}
      {inviteLink && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input readOnly value={inviteLink.link} onFocus={(e) => e.target.select()} style={{ minWidth: 320, flex: 1 }} />
          <button type="button" onClick={copyLink}>
            {copied ? "Zkopírováno ✓" : "Kopírovat odkaz"}
          </button>
        </div>
      )}
    </div>
  );
}
