import { ArrowUp, AudioLines, BadgeCheck, ChevronDown, Crosshair, Mic, PlayCircle, ShieldAlert, Sparkles, Square, X, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { parseCommand } from "../lib/commands";
import { LunaVoice, speak, type VoiceStatus } from "../lib/realtime";
import type { AskResponse, Audience, Command, KeyMoment, View } from "../lib/types";
import TraceView from "./TraceView";

interface Msg { role: "user" | "luna" | "system"; text: string; res?: AskResponse; via?: "voice" | "text" }
const TIER: Record<string, string> = { T0: "Match data", T1: "Quick judgement", T2: "Verified summary", T3: "Tactical analysis", T4: "Studio workflow", R: "Visual replay", BLOCKED: "Safety guard" };
const STATUS_LABEL: Record<VoiceStatus, string> = { idle: "Match intelligence", connecting: "Connecting voice…", listening: "Listening", thinking: "Thinking", speaking: "Speaking", error: "Voice error" };
const VOICE_HINTS = ["“Show me the last goal from the keeper's view”", "“Why did momentum change?”", "“Next moment”", "“Open studio”", "“Play” / “Pause”"];
const short = (t: string) => t.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ");

export default function AskPanel({ matchId, audience, setAudience, playbackT, focus, clearFocus, onReplay, onCommand, externalPrompt, voiceToggle, onVoiceStatus }:
  { matchId: string; audience: Audience; setAudience: (a: Audience) => void; playbackT: number | null; focus: KeyMoment | null; clearFocus: () => void;
    onReplay: (rid: string, view?: View) => void; onCommand: (c: Command) => string; externalPrompt: { text: string; n: number } | null;
    voiceToggle: number; onVoiceStatus: (s: VoiceStatus) => void }) {
  const { me } = useAuth();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [vs, setVs] = useState<VoiceStatus>("idle");
  const [mode, setMode] = useState<"realtime" | "browser" | null>(null);
  const [voiceErr, setVoiceErr] = useState<string | null>(null);
  const [openTrace, setOpenTrace] = useState<number | null>(null);
  const voice = useRef<LunaVoice | null>(null);
  const ctx = useRef({ audience, playbackT, focus, onCommand, onReplay });
  ctx.current = { audience, playbackT, focus, onCommand, onReplay };
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { listRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [msgs, busy]);
  useEffect(() => () => voice.current?.stop(), []);
  useEffect(() => { if (externalPrompt) submit(externalPrompt.text); /* eslint-disable-next-line */ }, [externalPrompt?.n]);
  useEffect(() => { if (voiceToggle) toggleVoice(); /* eslint-disable-next-line */ }, [voiceToggle]);
  useEffect(() => { onVoiceStatus(vs); }, [vs, onVoiceStatus]);

  const push = (m: Msg) => setMsgs((x) => [...x, m]);
  const suggestions = focus
    ? focus.type === "goal" ? ["Why did this goal happen?", "Show it from the keeper's view", "Who assisted it?"] : ["What changed after this?", "Was this the turning point?", "Explain it simply"]
    : ["Catch me up", "Why did momentum change?", "Show the winning goal", "Who changed the match?"];

  async function runAsk(question: string, via: "voice" | "text" = "text", goal_number?: number, view?: View) {
    const c = ctx.current;
    const res = await api.ask(matchId, question, c.audience, c.playbackT, c.focus?.id, goal_number, view);
    push({ role: "luna", text: res.answer, res, via });
    if (res.action?.type === "open_replay") c.onReplay(res.action.replay_id, res.action.view);
    if (via === "text" && c.audience === "accessible") speak(res.answer);
    return res;
  }
  function runCommand(cmd: Command, via: "voice" | "text") {
    const msg = ctx.current.onCommand(cmd);
    push({ role: "system", text: msg, via });
    return msg;
  }
  async function submit(text?: string) {
    const question = (text ?? q).trim();
    if (!question || busy) return;
    setQ(""); push({ role: "user", text: question });
    const cmd = parseCommand(question);
    if (cmd) { runCommand(cmd, "text"); return; }
    setBusy(true);
    try {
      if (mode === "realtime" && voice.current?.running) await voice.current.sayText(question);
      else await runAsk(question);
    } catch (e: any) { push({ role: "luna", text: e.status === 429 ? "You're asking quickly. Give me a few seconds." : `I couldn't complete that: ${e.message}` }); }
    finally { setBusy(false); }
  }

  async function toggleVoice() {
    if (voice.current?.running) { voice.current.stop(); voice.current = null; setMode(null); return; }
    setVoiceErr(null);
    voice.current = new LunaVoice({
      onStatus: (s, d) => { setVs(s); if (s === "error") setVoiceErr(d ?? "Voice unavailable"); },
      onMode: (m) => { setMode(m); if (m === "realtime") push({ role: "system", text: "Voice connected · GPT Realtime" }); },
      onTranscript: (role, text) => { if (role === "user") push({ role: "user", text, via: "voice" }); },
      onUtterance: async (text) => {
        const cmd = parseCommand(text);
        if (cmd) return runCommand(cmd, "voice");
        const r = await runAsk(text, "voice");
        return short(r.answer);
      },
      onTool: async (name, args) => {
        if (name === "ask_match") { const r = await runAsk(args.question, "voice"); return { answer: r.answer, verified: r.verification?.verdict }; }
        if (name === "show_replay") {
          const r = await runAsk(`Show goal ${args.goal_number}`, "voice", args.goal_number, args.view);
          return { opened: !!r.action, description: r.answer };
        }
        if (name === "control_app") return { done: runCommand({ action: args.action, value: args.value }, "voice") };
        return { error: "unknown tool" };
      },
    });
    await voice.current.start(matchId);
  }

  const live = voice.current?.running && vs !== "error";
  const first = me?.name.split(" ")[0];
  return (
    <div className="luna">
      <div className="luna-head">
        <div className="luna-id"><span className={`luna-orb s-${vs}`} /><div><b>Luna</b><small>{STATUS_LABEL[vs]}{mode && live ? ` · ${mode === "realtime" ? "GPT Realtime" : "browser speech"}` : ""}</small></div></div>
        <label className="select-pill"><span className="sr-only">Explain for</span>
          <select value={audience} onChange={(e) => setAudience(e.target.value as Audience)}>
            <option value="fan">Fan</option><option value="new_fan">New to football</option><option value="tactical">Tactical</option><option value="broadcaster">Broadcaster</option><option value="accessible">Audio-first</option>
          </select><ChevronDown size={14} /></label>
      </div>
      {focus && <div className="context-chip"><Crosshair size={14} /><span>Focused on <b>{focus.clock} {focus.headline}</b></span><button onClick={clearFocus} aria-label="Clear focus"><X size={13} /></button></div>}
      <div className="luna-thread" ref={listRef} aria-live="polite">
        {msgs.length === 0 && (
          <div className="luna-welcome"><Sparkles size={22} /><h3>{first ? `Hi ${first}, talk to the match.` : "Talk to the match."}</h3>
            <p>Press the mic (or <kbd>V</kbd>) and speak. I answer from verified match data and can drive the app for you.</p>
            <ul className="hint-list">{VOICE_HINTS.map((h) => <li key={h}>{h}</li>)}</ul></div>
        )}
        {msgs.map((m, i) => m.role === "system" ? (
          <div key={i} className="sys-line"><Zap size={12} />{m.text}</div>
        ) : (
          <div key={i} className={`bubble-wrap ${m.role}`}>
            <div className={`bubble ${m.res?.tier === "BLOCKED" ? "blocked" : ""}`}>{m.via === "voice" && m.role === "user" && <Mic size={12} className="inline-ico" />}{m.text}</div>
            {m.res && (<>
              <div className="meta">
                <span className={`tier t-${m.res.tier}`}>{TIER[m.res.tier] ?? m.res.tier}</span>
                {m.res.tier === "BLOCKED" ? <span className="warn"><ShieldAlert size={12} />Blocked</span>
                  : m.res.verification?.verdict === "approved" ? <span className="ok"><BadgeCheck size={12} />Verified</span> : <span className="warn">Unverified</span>}
                <span className="muted">{m.res.latency_ms} ms</span>
                <button onClick={() => setOpenTrace(openTrace === i ? null : i)}>{openTrace === i ? "Hide" : "How it worked"}</button>
              </div>
              {m.res.evidence.length > 0 && <div className="evidence">{m.res.evidence.slice(0, 4).map((e, k) => <span key={k} title={e.event_ids.join(", ")}>{e.label}<b>{String(e.value ?? "")}</b></span>)}</div>}
              {m.res.action?.type === "suggest_replay" && <button className="link-action" onClick={() => onReplay(m.res!.action!.replay_id)}><PlayCircle size={14} />Watch the visual proof</button>}
              {openTrace === i && <TraceView trace={m.res.trace} />}
            </>)}
          </div>
        ))}
        {busy && <div className="bubble-wrap luna"><div className="bubble typing"><i /><i /><i /></div></div>}
      </div>
      <div className="suggest">{suggestions.map((s) => <button key={s} onClick={() => submit(s)}>{s}</button>)}</div>
      <div className="composer">
        <button className={`mic ${live ? "on" : ""} s-${vs}`} onClick={toggleVoice} aria-label={live ? "Stop voice" : "Talk to Luna"} title="Talk to Luna (V)">{live ? <Square size={16} /> : <Mic size={18} />}</button>
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder={live ? "Listening… or type a question or command" : "Ask a question or type a command"} aria-label="Ask Luna" maxLength={600} />
        <button className="send" onClick={() => submit()} disabled={busy || !q.trim()} aria-label="Send"><ArrowUp size={18} /></button>
      </div>
      <div className="voice-line">{voiceErr ? <span className="warn">{voiceErr}</span> : live ? <><span className={`wave s-${vs}`}><i /><i /><i /><i /></span>{STATUS_LABEL[vs]}</> : <><AudioLines size={12} />GPT Realtime voice with browser-speech fallback · answers checked by the Evidence Referee</>}</div>
    </div>
  );
}
