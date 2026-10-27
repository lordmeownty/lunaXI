import { ChevronLeft, ChevronRight, Lightbulb, MessageSquareText, PlayCircle, X } from "lucide-react";
import type { KeyMoment, MatchSummary } from "../lib/types";
import { MOMENT_LABEL } from "./MomentRail";

export default function FocusCard({ m, k, onWatch, onAsk, onClear, onStep }: { m: MatchSummary; k: KeyMoment | null; onWatch: (rid: string) => void; onAsk: (q: string) => void; onClear: () => void; onStep: (d: 1 | -1) => void }) {
  if (!k) return (
    <div className="card focus empty"><Lightbulb size={18} /><div><b>Pick a moment</b><p>Select a marker on the rail, a story item or a goal. Luna, the replay and the stats will follow it.</p></div></div>
  );
  const team = k.team === m.home.id ? m.home : m.away;
  const player = k.player ? m.players[k.player] : null;
  const rep = m.replays.find((r) => r.id === k.replay_id);
  return (
    <div className="card focus" style={{ ["--team" as any]: team.colour }}>
      <div className="focus-top">
        <span className="focus-type">{MOMENT_LABEL[k.type] ?? k.type} · {k.clock}</span>
        <div className="row tight">
          <button className="icon-btn ghost" onClick={() => onStep(-1)} aria-label="Previous moment"><ChevronLeft size={15} /></button>
          <button className="icon-btn ghost" onClick={() => onStep(1)} aria-label="Next moment"><ChevronRight size={15} /></button>
          <button className="icon-btn ghost" onClick={onClear} aria-label="Clear focus"><X size={14} /></button>
        </div>
      </div>
      <h3>{k.headline}</h3>
      <p className="muted">{team.name}{player ? ` · #${player.number} ${player.name}` : ""}{k.score ? ` · ${k.score.home}–${k.score.away}` : ""}</p>
      {rep && <div className="focus-facts"><span><b>{rep.summary_facts.passes}</b> passes</span><span><b>{rep.summary_facts.duration_s}s</b> build-up</span><span><b>{rep.summary_facts.xg}</b> xG</span></div>}
      <div className="focus-actions">
        {rep && <button className="btn primary" onClick={() => onWatch(rep.id)}><PlayCircle size={16} />Watch in 3D</button>}
        <button className="btn" onClick={() => onAsk(k.type === "goal" ? "Why did this goal happen?" : "What changed after this moment?")}><Lightbulb size={16} />Explain</button>
        <button className="btn ghost" onClick={() => onAsk("Catch me up on what happened around this moment")}><MessageSquareText size={16} />Catch me up</button>
      </div>
    </div>
  );
}
