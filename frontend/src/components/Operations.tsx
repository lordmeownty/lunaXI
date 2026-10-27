import { Activity, Boxes, CloudUpload, Coins, GitBranch, KeyRound, Lock, ScrollText, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import AgentFlow from "./AgentFlow";
import TraceView from "./TraceView";

const FORMATION = [[9], [11, 10, 7], [5, 6], [3, 4, 8, 2], [1]];

export default function Operations({ matchId }: { matchId: string }) {
  const [cr, setCr] = useState<any>(null);
  const [audit, setAudit] = useState<any>(null);
  const [pub, setPub] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => { api.controlRoom().then((d) => alive && setCr(d)).catch(() => {}); api.audit().then((d) => alive && setAudit(d)).catch(() => {}); };
    load(); const id = setInterval(load, 4000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  if (!cr) return <div className="card"><div className="spinner" /></div>;
  const e = cr.efficiency, sec = cr.security, byNo = Object.fromEntries(cr.agents.map((a: any) => [a.no, a]));
  const publish = async () => { setPub("Publishing…"); try { const r = await api.publishEvents(matchId); setPub(`${r.sent} events → ${r.mode === "eventhub" ? "Azure Event Hubs" : "local outbox (Event Hubs not configured yet)"}`); } catch (er: any) { setPub(er.message); } };
  return (
    <div className="ops">
      <div className="kpi-row">
        <div className="kpi"><Activity size={16} /><b>{e.requests}</b><span>Requests answered</span></div>
        <div className="kpi"><Boxes size={16} /><b>{e.advanced_calls_avoided}</b><span>Reasoning calls avoided</span></div>
        <div className="kpi"><Coins size={16} /><b>${e.measured_cost_usd}</b><span>Measured AI cost</span></div>
        <div className="kpi"><Coins size={16} /><b>${cr.budget.remaining_usd}</b><span>Budget left today</span></div>
        <div className="kpi"><Activity size={16} /><b>{e.p95_ms} ms</b><span>p95 latency</span></div>
        <div className="kpi"><ShieldCheck size={16} /><b>{e.referee_rejections}</b><span>Referee rejections</span></div>
      </div>
      <div className="ops-grid">
        <section className="card wide">
          <h3><GitBranch size={16} />Agent workflow <span className="pill">{cr.workflow.engine}</span></h3>
          <p className="muted small">Every question runs through this graph. Blue shows the path taken by the latest request.</p>
          <AgentFlow graph={cr.workflow} trace={cr.traces[0]?.trace} />
        </section>
        <section className="card">
          <h3>The Starting XI</h3>
          <div className="pitch-formation">{FORMATION.map((row, i) => <div key={i} className="f-row">{row.map((n) => <div key={n} className="agent" title={byNo[n].role}><span className="shirt">{n}</span><b>{byNo[n].name}</b><small>{byNo[n].kind}</small></div>)}</div>)}</div>
          <div className="tiers">{Object.entries(e.by_tier).map(([k, v]) => <span key={k} className={`tier t-${k}`}>{k} · {String(v)}</span>)}</div>
        </section>
        <section className="card">
          <h3><Lock size={16} />Security</h3>
          <dl className="kv">
            <div className="kv-row"><dt>Sign-in</dt><dd>{sec.identity}</dd></div>
            <div className="kv-row"><dt><KeyRound size={12} /> Key Vault</dt><dd>{sec.key_vault.status}</dd></div>
            {Object.entries(sec.key_vault.secrets).map(([k, v]) => <div key={k} className="kv-row sub"><dt>{k}</dt><dd>{String(v)}</dd></div>)}
            <div className="kv-row"><dt>Prompt Shields</dt><dd>{sec.prompt_shields}</dd></div>
            <div className="kv-row"><dt>Rate limit</dt><dd>{sec.rate_limit_per_min}/min per user</dd></div>
            <div className="kv-row"><dt>Live feed</dt><dd>{sec.stream_auth}</dd></div>
            <div className="kv-row"><dt>Voice</dt><dd>{sec.voice_auth}</dd></div>
            <div className="kv-row"><dt>Audit chain</dt><dd className={sec.audit_chain_valid ? "ok" : "bad"}>{sec.audit_chain_valid ? `Intact · ${sec.audit_records} records` : "Broken"}</dd></div>
          </dl>
        </section>
        <section className="card">
          <h3>Models in Microsoft Foundry</h3>
          <dl className="kv">{Object.entries(cr.models).map(([k, v]) => <div key={k} className="kv-row"><dt>{k}</dt><dd><code>{String(v)}</code></dd></div>)}</dl>
          <p className={`notice ${cr.foundry_connected ? "" : "warn"}`}>{cr.foundry_connected ? "Foundry connected" : "Offline deterministic mode: add keys to .env"}</p>
          <h3><CloudUpload size={16} />Event pipeline</h3>
          <button className="btn" onClick={publish}><CloudUpload size={16} />Stream this match to Event Hubs</button>
          {pub && <p className="notice">{pub}</p>}
        </section>
        <section className="card wide">
          <h3><ScrollText size={16} />Audit log</h3>
          <table className="audit"><thead><tr><th>Time</th><th>Who</th><th>Action</th><th>Target</th><th>Hash</th></tr></thead>
            <tbody>{(audit?.records ?? []).slice(0, 12).map((r: any) => <tr key={r.id}><td>{new Date(r.ts).toLocaleTimeString()}</td><td>{r.actor?.name} <small className="muted">{r.actor?.primary_role?.replace("Luna.", "")}{r.actor?.viewing_as ? " (preview)" : ""}</small></td><td>{r.action}</td><td>{r.target}</td><td><code>{r.hash}</code></td></tr>)}</tbody></table>
        </section>
        <section className="card wide">
          <h3>Recent agent traces</h3>
          {cr.traces.length === 0 && <p className="muted">Ask Luna something to see the XI at work.</p>}
          {cr.traces.slice(0, 3).map((t: any) => <details key={t.trace.id}><summary><span className={`tier t-${t.tier}`}>{t.tier}</span> {t.question} <span className="muted">· {t.user}</span></summary><TraceView trace={t.trace} /></details>)}
        </section>
      </div>
    </div>
  );
}
