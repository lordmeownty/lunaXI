import { CheckCircle2, Clock, Inbox, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Package } from "../lib/types";

export default function Approvals() {
  const { can, me, refresh } = useAuth();
  const [items, setItems] = useState<Package[]>([]);
  const [sel, setSel] = useState<Package | null>(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.packages().then((p) => { setItems(p); setSel((s) => p.find((x) => x.id === s?.id) ?? p.find((x) => x.status === "pending_review") ?? p[0] ?? null); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, []);
  async function decide(approve: boolean) { if (!sel) return; setErr(null); try { await api.decide(sel.id, approve, note); setNote(""); load(); refresh(); } catch (e: any) { setErr(e.message); } }
  const icon = (s: string) => s === "approved" ? <CheckCircle2 size={14} className="ok" /> : s === "pending_review" ? <Clock size={14} className="warn" /> : <XCircle size={14} className="bad" />;
  const own = sel?.submitted_by === me?.name;
  return (
    <div className="page-grid">
      <aside className="card config list">
        <h3>Package queue</h3>
        {items.length === 0 && <div className="placeholder small"><Inbox size={20} /><p>No packages yet. Submit one from Recaps.</p></div>}
        {items.map((p) => <button key={p.id} className={`queue-item ${sel?.id === p.id ? "on" : ""}`} onClick={() => setSel(p)}>{icon(p.status)}<div><b>{p.title}</b><small>{p.id} · {p.submitted_by}</small></div></button>)}
      </aside>
      <section className="card output">
        {!sel ? <div className="placeholder"><Inbox size={26} /><p>Select a package to review.</p></div> : <>
          <div className="out-head"><div><h3>{sel.title}</h3><p className="muted">{sel.id} · submitted by {sel.submitted_by} · {new Date(sel.submitted_at).toLocaleTimeString()}</p></div>
            <span className={`status ${sel.status === "approved" ? "ok" : sel.status === "pending_review" ? "warn" : "bad"}`}>{sel.status.replace("_", " ")}</span></div>
          <p className="recap-text">{sel.recap}</p>
          <h4>Talking points</h4><ul>{sel.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <p className="muted small"><ShieldCheck size={13} /> Evidence Referee: {sel.verification?.verdict} · grounding {sel.verification?.grounding_score ?? "-"}</p>
          {sel.status === "pending_review" && (can("package.approve") ? (
            <div className="decision">
              {own ? <p className="notice warn">Separation of duties: you submitted this package, so a different editor must approve it.</p> : <>
                <label className="field">Editor note<textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Optional note for the producer" /></label>
                <div className="row"><button className="btn primary" onClick={() => decide(true)}><CheckCircle2 size={16} />Approve for air</button><button className="btn danger" onClick={() => decide(false)}><XCircle size={16} />Request changes</button></div></>}
            </div>) : <p className="notice">Waiting for an editor. Approved packages are published by Azure Functions and editors are notified in Teams.</p>)}
          {err && <p className="notice bad">{err}</p>}
          <h4>History (audited)</h4>
          <ol className="history">{sel.history.map((h, i) => <li key={i}><b>{h.action.replace("_", " ")}</b> by {h.by}<span className="muted"> · {new Date(h.at).toLocaleTimeString()}</span>{h.note && <em> “{h.note}”</em>}</li>)}</ol>
        </>}
      </section>
    </div>
  );
}
