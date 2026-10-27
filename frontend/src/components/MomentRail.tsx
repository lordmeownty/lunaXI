/**
 * Moment Rail: the spine of the match workspace. Two team lanes over a 0–95' ruler. Selecting a moment focuses
 * Luna Lens, the Focus card, the Match Pulse marker, the story feed and Luna's context together.
 * Keyboard: ← / → step through moments when the rail has focus.
 */
import { ChevronLeft, ChevronRight, CircleDot, Repeat2, Shuffle, Square, TrendingUp, XCircle } from "lucide-react";
import type { KeyMoment, MatchSummary } from "../lib/types";
import Crest from "./Crest";

const ICON: Record<string, any> = { goal: CircleDot, substitution: Repeat2, tactical_change: Shuffle, red_card: Square, yellow_card: Square, big_chance_missed: XCircle, momentum_shift: TrendingUp };
export const MOMENT_LABEL: Record<string, string> = { goal: "Goal", substitution: "Substitution", tactical_change: "Tactical change", red_card: "Red card", yellow_card: "Yellow card", big_chance_missed: "Big chance", momentum_shift: "Momentum shift" };

export default function MomentRail({ m, moments, playheadMin, focusId, onSelect, onStep, live }:
  { m: MatchSummary; moments: KeyMoment[]; playheadMin: number | null; focusId: string | null; onSelect: (k: KeyMoment) => void; onStep: (d: 1 | -1) => void; live: boolean }) {
  const pct = (min: number) => `${Math.min(100, Math.max(0, (min / 96) * 100))}%`;
  const idx = moments.findIndex((k) => k.id === focusId);
  const lane = (side: "home" | "away") => {
    const team = side === "home" ? m.home : m.away;
    return (
      <div className={`rail-lane ${side}`}>
        <div className="lane-label"><Crest colour={team.colour} short={team.short} size={22} /><span>{team.short}</span></div>
        <div className="lane-track">
          <div className="lane-line" style={{ background: `linear-gradient(90deg, ${team.colour}55, ${team.colour}22)` }} />
          {moments.filter((k) => (k.team === m.home.id ? "home" : "away") === side).map((k) => {
            const Icon = ICON[k.type] ?? CircleDot;
            const locked = live && playheadMin != null && k.minute > playheadMin;
            return (
              <button key={k.id} className={`rail-marker t-${k.type} ${focusId === k.id ? "on" : ""}`} style={{ left: pct(k.minute + 0.5), ["--team" as any]: team.colour }}
                disabled={locked} onClick={() => onSelect(k)} aria-label={`${k.clock} ${MOMENT_LABEL[k.type] ?? k.type}: ${k.headline}`}>
                <Icon size={12} strokeWidth={2.6} />
                {k.type === "goal" && k.score && <span className="rail-score">{k.score.home}–{k.score.away}</span>}
                <span className="rail-tip"><b>{k.clock} · {MOMENT_LABEL[k.type] ?? k.type}</b>{k.headline}</span>
              </button>
            );
          })}
        </div>
      </div>
    );
  };
  return (
    <section className="moment-rail" aria-label="Match moments" tabIndex={0}
      onKeyDown={(e) => { if (e.key === "ArrowRight") { e.preventDefault(); onStep(1); } if (e.key === "ArrowLeft") { e.preventDefault(); onStep(-1); } }}>
      <header className="rail-head">
        <div><b>Match moments</b><span className="muted">Pick one: the replay, story, stats and Luna all follow it</span></div>
        <div className="rail-nav">
          <span className="muted small">{idx >= 0 ? `${idx + 1} of ${moments.length}` : `${moments.length} moments`}</span>
          <button className="icon-btn" onClick={() => onStep(-1)} aria-label="Previous moment"><ChevronLeft size={16} /></button>
          <button className="icon-btn" onClick={() => onStep(1)} aria-label="Next moment"><ChevronRight size={16} /></button>
        </div>
      </header>
      <div className="rail-body">
        {lane("home")}
        <div className="rail-ruler">
          <div className="ruler-pad" />
          <div className="ruler-track">
            {[0, 15, 30, 45, 60, 75, 90].map((t) => <span key={t} className={`tick ${t === 45 ? "ht" : ""}`} style={{ left: pct(t) }}>{t === 45 ? "HT" : `${t}'`}</span>)}
            {playheadMin != null && <><div className="ruler-progress" style={{ width: pct(playheadMin) }} /><div className="ruler-head" style={{ left: pct(playheadMin) }} /></>}
          </div>
        </div>
        {lane("away")}
      </div>
    </section>
  );
}
