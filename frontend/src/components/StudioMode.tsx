import { AudioLines, FileAudio, PlayCircle, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import type { Claim, MatchSummary } from "../lib/types";
import TraceView from "./TraceView";

export default function StudioMode({ match, onReplay }: { match: MatchSummary; onReplay: (rid: string) => void }) {
  const [lines, setLines] = useState<{ speaker: string; t_match?: number; text: string }[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [trace, setTrace] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const replayFor = (ids: string[]) => match.replays.find((r) => r.goal_event_id && ids.includes(r.goal_event_id))?.id;
  const n = (v: string) => claims.filter((c) => c.verdict === v).length;
  async function run(fn: () => Promise<void>) { setBusy(true); setErr(null); try { await fn(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } }
  return (
    <div className="page-grid">
      <aside className="card config">
        <h3>Commentary check</h3>
        <p className="muted small">GPT Transcribe turns commentary audio into text, the Studio Producer extracts factual claims, and the Evidence Referee checks each one against the synthetic event data before it airs.</p>
        <button className="btn block" onClick={() => run(async () => { setClaims([]); setLines((await api.sampleCommentary(match.id)).lines); })} disabled={busy}><AudioLines size={16} />1 · Load sample commentary</button>
        <label className="btn block file"><FileAudio size={16} />…or upload audio<input type="file" accept="audio/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) run(async () => { const r = await api.transcribe(match.id, f); setLines(r.lines); setClaims(r.claims); setTrace(r.trace); }); }} /></label>
        <button className="btn primary block" onClick={() => run(async () => { const r = await api.verify(match.id, lines); setClaims(r.claims); setTrace(r.trace); })} disabled={busy || !lines.length}><ShieldCheck size={16} />{busy ? "Checking…" : "2 · Verify claims"}</button>
        {claims.length > 0 && <div className="tally"><span className="ok">{n("supported")} supported</span><span className="bad">{n("misleading")} misleading</span><span>{n("unverifiable")} unverifiable</span></div>}
      </aside>
      <section className="card output">
        {err && <p className="notice bad">{err}</p>}
        {lines.length === 0 && <div className="placeholder"><AudioLines size={26} /><p>Load the sample commentary or upload audio to begin. Try <b>The Controversial Finish</b> or <b>The Underdog</b>.</p></div>}
        <ol className="transcript">
          {lines.map((l, i) => (
            <li key={i}>
              <div className="speaker"><span className="avatar">{l.speaker.split(" ").pop()?.[0]}</span><b>{l.speaker}</b>{l.t_match != null && <span className="muted">{Math.floor(l.t_match / 60)}'</span>}</div>
              <p>“{l.text}”</p>
              {claims.filter((c) => Number(c.line) === i).map((c, k) => (
                <div key={k} className={`verdict v-${c.verdict}`}><span className="vtag">{c.verdict}</span><span>{c.proof}</span>
                  {replayFor(c.event_ids || []) && <button className="link" onClick={() => onReplay(replayFor(c.event_ids)!)}><PlayCircle size={14} />Show proof in 3D</button>}</div>
              ))}
            </li>
          ))}
        </ol>
        {trace && <details><summary>Agent trace</summary><TraceView trace={trace} /></details>}
      </section>
    </div>
  );
}
