import { BadgeCheck, Image as ImageIcon, Send, Sparkles, Volume2 } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { speak } from "../lib/realtime";
import type { Audience, RecapPackage } from "../lib/types";
import TraceView from "./TraceView";

const AUD: [Audience, string, string][] = [["fan", "Fan", "Lively 30-second story"], ["new_fan", "New fan", "Plain language, no jargon"], ["tactical", "Analyst", "Shape, space and numbers"], ["broadcaster", "Broadcaster", "Talking points for air"], ["accessible", "Audio-first", "Spatial audio description"]];

export default function RecapStudio({ matchId, playbackT, onReplay, onGoApprovals }: { matchId: string; playbackT: number | null; onReplay: (rid: string) => void; onGoApprovals: () => void }) {
  const { can, refresh } = useAuth();
  const [audience, setAudience] = useState<Audience>("fan");
  const [phase, setPhase] = useState<"half" | "full" | "live">(playbackT != null ? "live" : "full");
  const [pkg, setPkg] = useState<RecapPackage | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; link?: boolean } | null>(null);
  const [poster, setPoster] = useState<{ src?: string; note: string } | null>(null);
  const [trace, setTrace] = useState(false);

  async function build() { setBusy(true); setMsg(null); setPoster(null); try { setPkg(await api.recap(matchId, audience, phase, playbackT)); } catch (e: any) { setMsg({ text: e.message }); } finally { setBusy(false); } }
  async function submit() {
    try { const p = await api.submitPackage(matchId, phase === "half" ? "half-time package" : phase === "full" ? "full-time package" : "live package", phase === "live" ? playbackT : null);
      setMsg({ text: `Submitted ${p.id} for editorial approval · event sent via ${p.event?.mode === "servicebus" ? "Azure Service Bus" : "local outbox"}.`, link: true }); refresh(); }
    catch (e: any) { setMsg({ text: e.message }); }
  }
  async function makePoster() { setPoster({ note: "Generating artwork…" }); try { const r = await api.poster(matchId); setPoster({ src: r.b64 ? `data:image/png;base64,${r.b64}` : r.url, note: r.label }); } catch (e: any) { setPoster({ note: `Image model not available (${e.message})` }); } }

  return (
    <div className="page-grid">
      <aside className="card config">
        <h3>1 · Choose the moment</h3>
        <div className="segmented">{(["live", "half", "full"] as const).map((p) => <button key={p} className={phase === p ? "on" : ""} onClick={() => setPhase(p)}>{p === "live" ? "So far" : p === "half" ? "Half-time" : "Full-time"}</button>)}</div>
        <h3>2 · Choose the audience</h3>
        <fieldset className="field">{AUD.map(([a, l, d]) => <label key={a} className={`aud ${audience === a ? "on" : ""}`}><input type="radio" name="aud" checked={audience === a} onChange={() => setAudience(a)} /><b>{l}</b><small>{d}</small></label>)}</fieldset>
        <button className="btn primary block" onClick={build} disabled={busy}><Sparkles size={16} />{busy ? "Agents working…" : "3 · Generate recap"}</button>
      </aside>
      <section className="card output">
        {!pkg && <div className="placeholder"><Sparkles size={26} /><p>One verified match package, shaped for every audience.</p></div>}
        {pkg && <>
          <div className="out-head"><div className="out-score">{pkg.score.home}<span>–</span>{pkg.score.away}</div>
            <span className={`status ${pkg.verification?.verdict === "approved" ? "ok" : "warn"}`}><BadgeCheck size={14} />Evidence Referee: {pkg.verification?.verdict}</span></div>
          <p className="recap-text">{pkg.recap}</p>
          <div className="row">
            <button className="btn" onClick={() => speak(pkg.recap)}><Volume2 size={16} />Listen</button>
            <button className="btn" onClick={makePoster}><ImageIcon size={16} />Poster art</button>
            {can("package.submit") && <button className="btn primary" onClick={submit}><Send size={16} />Submit for editorial approval</button>}
            <button className="btn ghost" onClick={() => setTrace(!trace)}>Agent trace</button>
          </div>
          {msg && <p className="notice">{msg.text} {msg.link && <button className="link" onClick={onGoApprovals}>Open approvals →</button>}</p>}
          <div className="three-col">
            <div><h4>Talking points</h4><ul>{pkg.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul></div>
            <div><h4>Replay reel</h4><ul>{pkg.replay_reel.map((r) => <li key={r.id}><button className="link" onClick={() => onReplay(r.id)}>{r.clock} · {r.title}</button></li>)}</ul></div>
            <div><h4>Standouts</h4><ul>{pkg.top_players.map((p, i) => <li key={i}>{p.name} <span className="muted">{p.team}</span></li>)}</ul></div>
          </div>
          {poster && <figure className="poster">{poster.src && <img src={poster.src} alt="AI-generated match poster" />}<figcaption>{poster.note}</figcaption></figure>}
          {trace && pkg.trace && <TraceView trace={pkg.trace} />}
        </>}
      </section>
    </div>
  );
}
