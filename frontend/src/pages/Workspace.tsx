import { ArrowLeft, BarChart3, Bell, ChevronDown, ChevronRight, ClipboardCheck, Eye, Gauge, Home as HomeIcon, MessagesSquare, Mic, Newspaper, Pause, Play, Radio, RotateCcw, Sparkles, Tv } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Approvals from "../components/Approvals";
import AskPanel from "../components/AskPanel";
import Brand from "../components/Brand";
import Crest from "../components/Crest";
import FocusCard from "../components/FocusCard";
import LunaLens from "../components/LunaLens";
import MomentRail from "../components/MomentRail";
import MomentumChart from "../components/MomentumChart";
import Operations from "../components/Operations";
import RecapStudio from "../components/RecapStudio";
import StatsCompare from "../components/StatsCompare";
import StudioMode from "../components/StudioMode";
import UserMenu from "../components/UserMenu";
import { api } from "../lib/api";
import { ROLE_LABEL, useAuth } from "../lib/auth";
import type { VoiceStatus } from "../lib/realtime";
import type { Audience, Command, KeyMoment, MatchIndexItem, MatchSummary, Surface, View } from "../lib/types";

interface FeedItem { id: string; clock: string; text: string; type?: string; momentId?: string }
const SECTION_LABEL: Record<Surface, string> = { match: "Match", recaps: "Recaps", studio: "Broadcast Studio", approvals: "Approvals", operations: "Operations" };
const NEEDS: Record<Surface, string> = { match: "match.view", recaps: "recap.create", studio: "studio.use", approvals: "package.submit", operations: "ops.view" };

export default function Workspace({ matchId, surface, go }: { matchId: string; surface: Surface; go: (id: string | null, s?: Surface) => void }) {
  const { can, me, viewAs, setViewAs } = useAuth();
  const [m, setM] = useState<MatchSummary | null>(null);
  const [all, setAll] = useState<MatchIndexItem[]>([]);
  const [mode, setMode] = useState<"live" | "full">("full");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(240);
  const [t, setT] = useState(0);
  const [clock, setClock] = useState("FT");
  const [score, setScore] = useState({ home: 0, away: 0 });
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [series, setSeries] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [shifts, setShifts] = useState<any[]>([]);
  const [replayId, setReplayId] = useState<string | null>(null);
  const [view, setView] = useState<View>("broadcast");
  const [playKey, setPlayKey] = useState(0);
  const [audience, setAudience] = useState<Audience>(me?.primary_role === "Luna.Analyst" ? "tactical" : me?.primary_role === "Luna.Broadcaster" ? "broadcaster" : "fan");
  const [lunaOpen, setLunaOpen] = useState(true);
  const [focus, setFocus] = useState<KeyMoment | null>(null);
  const [prompt, setPrompt] = useState<{ text: string; n: number } | null>(null);
  const [voiceToggle, setVoiceToggle] = useState(0);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [switcher, setSwitcher] = useState(false);
  const es = useRef<EventSource | null>(null);
  const tRef = useRef(0), statsTick = useRef(0);

  useEffect(() => { api.match(matchId).then(setM); api.matches().then(setAll).catch(() => {}); return () => es.current?.close(); }, [matchId]);

  const loadFull = useCallback(async () => {
    if (!m) return;
    es.current?.close(); setPlaying(false);
    const s = await api.stats(matchId);
    setSeries(s.momentum); setStats(s.stats); setShifts(s.shifts); setScore(m.final_score); setClock("FT");
    setT(m.duration_s); tRef.current = m.duration_s;
    setFeed(m.key_moments.map((k) => ({ id: k.id, momentId: k.id, clock: k.clock, text: k.headline, type: k.type })).reverse());
    setReplayId((r) => r ?? m.replays[m.replays.length - 1]?.id ?? null);
  }, [m, matchId]);
  useEffect(() => { if (m && mode === "full") loadFull(); }, [mode, m, loadFull]);

  const play = useCallback(async () => {
    if (!m) return;
    es.current?.close();
    const src = new EventSource(await api.streamUrl(matchId, speed, tRef.current));
    es.current = src; setPlaying(true);
    src.onmessage = (msg) => {
      const d = JSON.parse(msg.data);
      if (d.kind === "event") {
        const e = d.event; tRef.current = e.t; setT(e.t); setClock(e.clock); setScore(d.score);
        if (["save", "half_time", "full_time"].includes(e.type) || (e.type === "shot" && (e.xg ?? 0) >= 0.25 && e.outcome !== "goal")) {
          const who = e.player ? m.players[e.player]?.name : "";
          const text = e.type === "shot" ? `Chance for ${who} · xG ${e.xg} · ${String(e.outcome).replace("_", " ")}` : e.type === "save" ? `Save by ${who}` : e.note;
          setFeed((f) => [{ id: e.id, clock: e.clock, text, type: e.type }, ...f].slice(0, 80));
        }
      } else if (d.kind === "narrative") {
        const km = d.moment;
        setFeed((f) => [{ id: `n-${f.length}-${d.clock}`, momentId: km?.id, clock: d.clock, text: d.text, type: km?.type }, ...f].slice(0, 80));
        if (km?.replay_id) { setReplayId(km.replay_id); setFocus(km); setPlayKey((x) => x + 1); }
      } else if (d.kind === "momentum") {
        setSeries(d.series);
        if (++statsTick.current % 2 === 0) api.stats(matchId, d.t).then((s) => { setStats(s.stats); setShifts(s.shifts); });
      } else if (d.kind === "end") { src.close(); setPlaying(false); }
    };
    src.onerror = () => { src.close(); setPlaying(false); };
  }, [m, matchId, speed]);
  const pause = () => { es.current?.close(); setPlaying(false); };
  const restart = () => { pause(); tRef.current = 0; setT(0); setClock("0'"); setScore({ home: 0, away: 0 }); setFeed([]); setSeries([]); setStats(null); setShifts([]); setReplayId(null); setFocus(null); };

  const moments = useMemo<KeyMoment[]>(() => {
    if (!m) return [];
    const sh = shifts.map((s: any) => ({ id: `shift-${s.at_min}`, type: "momentum_shift", minute: s.at_min, clock: `${s.at_min}'`, team: s.towards === "home" ? m.home.id : m.away.id,
      player: null, headline: `Momentum swings to ${s.towards === "home" ? m.home.name : m.away.name}`, event_ids: [] }));
    return [...m.key_moments, ...sh].sort((a, b) => a.minute - b.minute).filter((k) => mode === "full" || k.minute * 60 <= t + 30);
  }, [m, shifts, mode, t]);

  const selectMoment = useCallback((k: KeyMoment) => { setFocus(k); if (k.replay_id) { setReplayId(k.replay_id); setPlayKey((x) => x + 1); } if (surface !== "match") go(matchId, "match"); }, [surface, go, matchId]);
  const step = useCallback((d: 1 | -1) => {
    if (!moments.length) return null;
    const i = focus ? moments.findIndex((k) => k.id === focus.id) : -1;
    const next = moments[Math.max(0, Math.min(moments.length - 1, i + d))];
    selectMoment(next);
    return next;
  }, [moments, focus, selectMoment]);
  const openReplay = (rid: string, v?: View) => {
    setReplayId(rid); if (v) setView(v); setPlayKey((x) => x + 1);
    const km = m?.key_moments.find((k) => k.replay_id === rid); if (km) setFocus(km);
    if (surface !== "match") go(matchId, "match");
  };
  const askLuna = (text: string) => { setLunaOpen(true); setPrompt({ text, n: Date.now() }); };

  /** Single entry point for voice/text commands. Returns a short confirmation Luna can speak. */
  const onCommand = useCallback((c: Command): string => {
    switch (c.action) {
      case "play": if (mode !== "live") { setMode("live"); restart(); setTimeout(play, 150); return "Starting the live simulation."; } play(); return "Playing.";
      case "pause": pause(); return "Paused.";
      case "restart": restart(); return "Back to kick-off.";
      case "next_moment": { const k = step(1); return k ? `${k.clock}: ${k.headline}.` : "No moments yet."; }
      case "previous_moment": { const k = step(-1); return k ? `${k.clock}: ${k.headline}.` : "No moments yet."; }
      case "set_speed": { const v = Number(c.value) || 240; setSpeed(v); if (playing) { pause(); setTimeout(play, 100); } return `Speed set to ${v}×.`; }
      case "set_view": { const v = (c.value as View) || "broadcast"; setView(v); setPlayKey((x) => x + 1); return `Switched to the ${v.replace("_", " ")} view.`; }
      case "set_audience": setAudience((c.value as Audience) || "fan"); return `I'll explain things for a ${String(c.value).replace("_", " ")} audience.`;
      case "open_section": {
        const s = (c.value as Surface) || "match";
        if (!can(NEEDS[s])) return `Your current role can't open ${SECTION_LABEL[s] ?? s}.`;
        go(matchId, s); return `Opening ${SECTION_LABEL[s]}.`;
      }
      case "open_match": {
        const q = String(c.value || "").toLowerCase();
        const hit = all.find((x) => x.title.toLowerCase().includes(q) || q.split(" ").some((w) => w.length > 3 && (x.title.toLowerCase().includes(w) || x.home.name.toLowerCase().includes(w) || x.away.name.toLowerCase().includes(w))));
        if (!hit) return `I couldn't find a match called ${c.value}.`;
        go(hit.id); return `Opening ${hit.title}.`;
      }
    }
    return "Done.";
  }, [mode, playing, play, step, can, go, matchId, all]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key.toLowerCase() === "v") { setLunaOpen(true); setVoiceToggle(Date.now()); }
      if (e.key === " " && mode === "live" && surface === "match") { e.preventDefault(); playing ? pause() : play(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, playing, play, surface]);

  if (!m) return <main className="loading-screen"><Brand /><div className="spinner" /><span>Preparing the match…</span></main>;
  const live = mode === "live", playbackT = live ? t : null;
  const nav: { id: Surface; label: string; icon: any }[] = [{ id: "match", label: "Match", icon: Tv }, { id: "recaps", label: "Recaps", icon: Sparkles },
    { id: "studio", label: "Studio", icon: Newspaper }, { id: "approvals", label: "Approvals", icon: ClipboardCheck }, { id: "operations", label: "Operations", icon: Gauge }];
  const allowed = can(NEEDS[surface]);
  const pending = me?.pending_approvals ?? 0;

  return (
    <div className={`shell ${lunaOpen ? "luna-open" : ""}`}>
      <aside className="rail" aria-label="Workspace navigation">
        <button className="rail-logo" onClick={() => go(null)} aria-label="Home"><Brand compact /></button>
        <nav>{nav.map((n) => {
          const ok = can(NEEDS[n.id]);
          return <button key={n.id} className={surface === n.id ? "on" : ""} disabled={!ok} title={ok ? n.label : `Not available for ${ROLE_LABEL[me?.primary_role ?? "Luna.Fan"]}`} onClick={() => go(matchId, n.id)} aria-current={surface === n.id}>
            <n.icon size={20} /><span>{n.label}</span>{n.id === "approvals" && pending > 0 && ok && <em className="badge-dot">{pending}</em>}</button>;
        })}</nav>
        <button className={`rail-luna ${lunaOpen ? "on" : ""}`} onClick={() => setLunaOpen(!lunaOpen)} aria-pressed={lunaOpen}><MessagesSquare size={20} /><span>Luna</span></button>
      </aside>

      <div className="main">
        {viewAs && <div className="preview-banner"><Eye size={14} />Previewing as <b>{ROLE_LABEL[viewAs]}</b>: you see exactly what this role sees. <button onClick={() => setViewAs(null)}>Exit preview</button></div>}
        <header className="appbar">
          <div className="ab-left">
            <button className="icon-btn" onClick={() => go(null)} aria-label="Back to home"><ArrowLeft size={18} /></button>
            <nav className="crumbs" aria-label="Breadcrumb">
              <button onClick={() => go(null)}><HomeIcon size={13} />Home</button><ChevronRight size={13} />
              <div className="switch">
                <button onClick={() => setSwitcher(!switcher)} aria-expanded={switcher}>{m.title}<ChevronDown size={13} /></button>
                {switcher && <div className="menu switch-menu" onMouseLeave={() => setSwitcher(false)}>{all.map((x) => (
                  <button key={x.id} className={`menu-item ${x.id === matchId ? "on" : ""}`} onClick={() => { setSwitcher(false); go(x.id, surface); }}>
                    <Crest colour={x.home.colour} short={x.home.short} size={20} /><span><b>{x.title}</b><small>{x.home.short} {x.final_score.home}–{x.final_score.away} {x.away.short}</small></span></button>))}</div>}
              </div>
              {surface !== "match" && <><ChevronRight size={13} /><span>{SECTION_LABEL[surface]}</span></>}
            </nav>
          </div>
          <div className="scoreboard" aria-live="polite">
            <span className="sb-team"><Crest colour={m.home.colour} short={m.home.short} size={32} /><b>{m.home.name}</b></span>
            <span className="sb-score">{score.home}<i>–</i>{score.away}</span>
            <span className="sb-team away"><b>{m.away.name}</b><Crest colour={m.away.colour} short={m.away.short} size={32} /></span>
            <span className={`sb-clock ${live && playing ? "live" : ""}`}>{live && playing && <Radio size={12} />}{clock}</span>
          </div>
          <div className="ab-right">
            {can("package.approve") && <button className="icon-btn bell" onClick={() => go(matchId, "approvals")} aria-label={`${pending} approvals waiting`} title="Approvals waiting"><Bell size={17} />{pending > 0 && <em>{pending}</em>}</button>}
            <UserMenu compact />
          </div>
        </header>

        {!allowed && <Page title="Not available" kicker="Role-based access" sub={`${ROLE_LABEL[me?.primary_role ?? "Luna.Fan"]} can't open ${SECTION_LABEL[surface]}.`}><button className="btn primary" onClick={() => go(matchId)}>Back to the match</button></Page>}

        {allowed && surface === "match" && (
          <div className="match-view">
            <div className="matchbar">
              <div className="segmented" role="tablist" aria-label="Viewing mode">
                <button className={!live ? "on" : ""} onClick={() => setMode("full")}>Full match</button>
                <button className={live ? "on" : ""} onClick={() => { setMode("live"); restart(); }}>Live simulation</button>
              </div>
              {live && <div className="transport">
                <button className="btn primary" onClick={playing ? pause : play}>{playing ? <Pause size={16} /> : <Play size={16} />}{playing ? "Pause" : t > 0 ? "Resume" : "Kick off"}</button>
                <button className="icon-btn" onClick={restart} aria-label="Restart"><RotateCcw size={16} /></button>
                <label className="select-pill"><span className="sr-only">Speed</span><select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={60}>60×</option><option value={240}>240×</option><option value={600}>600×</option></select><ChevronDown size={14} /></label>
              </div>}
              <p className="story-line">{live ? "Live: synthetic events stream over a secure ticketed feed. Luna never spoils what hasn't happened." : m.story}</p>
            </div>
            <MomentRail m={m} moments={moments} playheadMin={live ? t / 60 : null} focusId={focus?.id ?? null} onSelect={selectMoment} onStep={(d) => { step(d); }} live={live} />
            <div className="stage">
              <section className="stage-main">
                <div className="lens-wrap">
                  <LunaLens matchId={matchId} replayId={replayId} view={view} setView={setView} playKey={playKey} />
                  <button className={`voice-fab s-${voiceStatus}`} onClick={() => { setLunaOpen(true); setVoiceToggle(Date.now()); }} aria-label="Talk to Luna">
                    <Mic size={18} /><span>{voiceStatus === "idle" || voiceStatus === "error" ? "Talk to Luna" : voiceStatus === "listening" ? "Listening…" : voiceStatus === "thinking" ? "Thinking…" : voiceStatus === "speaking" ? "Speaking…" : "Connecting…"}</span><kbd>V</kbd>
                  </button>
                </div>
                <div className="goal-reel" aria-label="Goal replays">
                  {m.replays.map((r) => {
                    const ok = !live || r.minute * 60 <= t;
                    const team = r.team === m.home.id ? m.home : m.away;
                    return <button key={r.id} disabled={!ok} className={replayId === r.id ? "on" : ""} onClick={() => openReplay(r.id)} style={{ ["--team" as any]: team.colour }}>
                      <span className="gr-n">G{r.goal_number}</span><span className="gr-t"><b>{ok ? `${r.clock} · ${team.short}` : "–"}</b><small>{ok ? m.players[r.scorer]?.name : "Not reached"}</small></span></button>;
                  })}
                </div>
              </section>
              <section className="stage-side">
                <FocusCard m={m} k={focus} onWatch={(rid) => openReplay(rid)} onAsk={askLuna} onClear={() => setFocus(null)} onStep={(d) => { step(d); }} />
                <div className="card"><div className="card-title"><BarChart3 size={16} /><b>Match pulse</b><small>{live ? `to ${clock}` : "full match"}</small></div>
                  <MomentumChart series={series} home={m.home.short} away={m.away.short} homeColour={m.home.colour} awayColour={m.away.colour} focusMin={focus ? focus.minute + 0.5 : null} />
                  <StatsCompare stats={stats} home={m.home} away={m.away} /></div>
                <div className="card story"><div className="card-title"><Newspaper size={16} /><b>Match story</b><small>{feed.length} items</small></div>
                  <ol className="feed">
                    {feed.length === 0 && <li className="muted">Kick off to watch the story build.</li>}
                    {feed.map((f) => {
                      const km = f.momentId ? m.key_moments.find((k) => k.id === f.momentId) : null;
                      return <li key={f.id} className={`t-${f.type} ${focus && km && focus.id === km.id ? "on" : ""}`}><time>{f.clock}</time>
                        <button className="feed-body" disabled={!km} onClick={() => km && selectMoment(km)}>{f.text}</button></li>;
                    })}
                  </ol></div>
              </section>
            </div>
          </div>
        )}
        {allowed && surface === "recaps" && <Page title="Recap Studio" kicker="Automated storytelling" sub="One verified package, shaped for every audience. Broadcasters submit it for approval from here."><RecapStudio matchId={matchId} playbackT={playbackT && playbackT > 0 ? playbackT : null} onReplay={openReplay} onGoApprovals={() => go(matchId, "approvals")} /></Page>}
        {allowed && surface === "studio" && <Page title="Broadcast Studio" kicker="Broadcaster workflow" sub="Transcribe commentary, check every claim and take the proof to air."><StudioMode match={m} onReplay={openReplay} /></Page>}
        {allowed && surface === "approvals" && <Page title="Editorial approvals" kicker="Enterprise workflow" sub="Nothing reaches air without an editor. Every decision is audited and published through Azure."><Approvals /></Page>}
        {allowed && surface === "operations" && <Page title="Operations" kicker="Platform governance" sub="Agent workflow, cost, security, Key Vault, audit and the Azure event pipeline."><Operations matchId={matchId} /></Page>}
      </div>

      {lunaOpen && <aside className="luna-drawer" aria-label="Luna assistant">
        <AskPanel matchId={matchId} audience={audience} setAudience={setAudience} playbackT={playbackT} focus={focus} clearFocus={() => setFocus(null)}
          onReplay={openReplay} onCommand={onCommand} externalPrompt={prompt} voiceToggle={voiceToggle} onVoiceStatus={setVoiceStatus} />
      </aside>}
    </div>
  );
}

function Page({ title, kicker, sub, children }: { title: string; kicker: string; sub: string; children: ReactNode }) {
  return <div className="page"><div className="page-head"><span className="eyebrow">{kicker}</span><h2>{title}</h2><p className="muted">{sub}</p></div>{children}</div>;
}
