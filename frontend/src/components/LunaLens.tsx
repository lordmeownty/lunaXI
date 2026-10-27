/**
 * Luna Lens: 3D reconstruction of a goal from synthetic keyframes.
 * Build-up passes → camera drops behind the shooter → curved shot → keeper / goal-mouth view.
 * The camera view is controlled by the workspace so voice commands ("keeper view") can change it.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import { Camera, Gauge, Pause, Play, RotateCcw, Target, Timer, Users } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { api } from "../lib/api";
import type { Kit, PlayerPos, ReplayFull, View } from "../lib/types";

const PASS_S = 1.2, SHOT_S = 1.4, HOLD_S = 2.8;
const SKIN = ["#f1d3b3", "#e0ac83", "#c68a5e", "#8d5a3b", "#5c3a24"];
const HAIR = ["#1b1410", "#3b2416", "#7a4a22", "#d8b46a"];
const P = (x: number, y: number, h = 0) => new THREE.Vector3(x - 52.5, h, y - 34);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

function useTimeline(rep: ReplayFull | null) {
  return useMemo(() => {
    if (!rep) return { total: 0, buildEnd: 0, shotEnd: 0, segs: 0 };
    const segs = Math.max(1, rep.frames.length - 1), buildEnd = segs * PASS_S, shotEnd = buildEnd + SHOT_S;
    return { total: shotEnd + HOLD_S, buildEnd, shotEnd, segs };
  }, [rep]);
}

function Stadium() {
  const lines: [number, number][][] = [[[0, 0], [105, 0], [105, 68], [0, 68], [0, 0]], [[52.5, 0], [52.5, 68]],
    [[0, 13.84], [16.5, 13.84], [16.5, 54.16], [0, 54.16]], [[105, 13.84], [88.5, 13.84], [88.5, 54.16], [105, 54.16]],
    [[0, 24.84], [5.5, 24.84], [5.5, 43.16], [0, 43.16]], [[105, 24.84], [99.5, 24.84], [99.5, 43.16], [105, 43.16]]];
  const circle = Array.from({ length: 65 }, (_, i) => { const a = (i / 64) * Math.PI * 2; return P(52.5 + Math.cos(a) * 9.15, 34 + Math.sin(a) * 9.15, 0.02); });
  const stands: [number, number, number, number][] = [[0, -50, 140, 14], [0, 50, 140, 14], [-74, 0, 14, 110], [74, 0, 14, 110]];
  return (
    <group>
      <mesh rotation-x={-Math.PI / 2} position={[0, -0.01, 0]}><planeGeometry args={[150, 112]} /><meshStandardMaterial color="#0d1f14" /></mesh>
      {Array.from({ length: 12 }, (_, i) => (
        <mesh key={i} rotation-x={-Math.PI / 2} position={[-52.5 + 4.375 + i * 8.75, 0, 0]}><planeGeometry args={[8.75, 68]} /><meshStandardMaterial color={i % 2 ? "#1d5a33" : "#226539"} roughness={0.95} /></mesh>
      ))}
      {lines.map((l, i) => <Line key={i} points={l.map(([x, y]) => P(x, y, 0.02))} color="#e8f5ec" lineWidth={1.6} transparent opacity={0.9} />)}
      <Line points={circle} color="#e8f5ec" lineWidth={1.6} transparent opacity={0.9} />
      {stands.map(([x, z, w, d], i) => (
        <group key={i} position={[x, 0, z]}>
          <mesh position={[0, 4, 0]}><boxGeometry args={[w, 8, d]} /><meshStandardMaterial color="#12161d" roughness={1} /></mesh>
          <mesh position={[0, 8.2, 0]}><boxGeometry args={[w, 0.4, d]} /><meshStandardMaterial color="#1f2937" emissive="#0b3a66" emissiveIntensity={0.35} /></mesh>
        </group>
      ))}
      {[[-66, -44], [66, -44], [-66, 44], [66, 44]].map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          <mesh position={[0, 14, 0]}><cylinderGeometry args={[0.35, 0.5, 28, 8]} /><meshStandardMaterial color="#374151" /></mesh>
          <mesh position={[0, 28.5, 0]}><boxGeometry args={[5, 2, 1]} /><meshStandardMaterial color="#f8fafc" emissive="#ffffff" emissiveIntensity={1.2} /></mesh>
        </group>
      ))}
      <Goal x={105} /><Goal x={0} />
    </group>
  );
}

function Goal({ x }: { x: number }) {
  const d = x > 50 ? 1 : -1;
  const post = (y: number) => <mesh position={P(x + d * 0.06, y, 1.22)}><cylinderGeometry args={[0.07, 0.07, 2.44, 12]} /><meshStandardMaterial color="#f8fafc" /></mesh>;
  return (
    <group>
      {post(30.34)}{post(37.66)}
      <mesh position={P(x + d * 0.06, 34, 2.44)} rotation-x={Math.PI / 2}><cylinderGeometry args={[0.07, 0.07, 7.32, 12]} /><meshStandardMaterial color="#f8fafc" /></mesh>
      <mesh position={P(x + d * 1.1, 34, 1.22)} rotation-y={Math.PI / 2}><planeGeometry args={[7.32, 2.44, 18, 6]} /><meshStandardMaterial color="#e2e8f0" wireframe transparent opacity={0.25} /></mesh>
      <mesh position={P(x + d * 1.1, 34, 2.44)} rotation-x={Math.PI / 2}><planeGeometry args={[2.2, 7.32, 6, 18]} /><meshStandardMaterial color="#e2e8f0" wireframe transparent opacity={0.18} /></mesh>
    </group>
  );
}

function GoalGrid({ rep, show }: { rep: ReplayFull; show: boolean }) {
  if (!show) return null;
  const gx = rep.shot.to.x, d = gx > 50 ? -0.05 : 0.05, ys = [30.34, 32.78, 35.22, 37.66], zs = [0, 0.81, 1.63, 2.44];
  const ci = Math.min(2, Math.max(0, Math.floor((rep.shot.to.y - 30.34) / 2.44))), cj = Math.min(2, Math.max(0, Math.floor(rep.shot.to.z / 0.814)));
  return (
    <group>
      {ys.map((y, i) => <Line key={"v" + i} points={[P(gx + d, y, 0), P(gx + d, y, 2.44)]} color="#479ef5" lineWidth={1.2} />)}
      {zs.map((z, i) => <Line key={"h" + i} points={[P(gx + d, 30.34, z), P(gx + d, 37.66, z)]} color="#479ef5" lineWidth={1.2} />)}
      <mesh position={P(gx + d, ys[ci] + 1.22, zs[cj] + 0.407)} rotation-y={Math.PI / 2}><planeGeometry args={[2.44, 0.814]} /><meshBasicMaterial color="#479ef5" transparent opacity={0.5} side={THREE.DoubleSide} /></mesh>
    </group>
  );
}

function Footballer({ kit, gk, skin, hair, heading, phase, speed, highlight, num, label }:
  { kit: Kit; gk: boolean; skin: number; hair: number; heading: number; phase: number; speed: number; highlight: boolean; num: number; label?: string }) {
  const shirt = gk ? kit.gk : kit.colour, shorts = gk ? "#111827" : kit.secondary, socks = gk ? kit.gk : kit.colour;
  const amp = Math.min(1, speed / 6) * 0.75 + 0.06, swing = Math.sin(phase) * amp, bob = Math.abs(Math.cos(phase)) * 0.05 * amp;
  const skinC = SKIN[skin % SKIN.length], hairC = HAIR[hair % HAIR.length];
  return (
    <group rotation-y={heading}>
      <mesh rotation-x={-Math.PI / 2} position={[0, 0.015, 0]}><circleGeometry args={[0.5, 20]} /><meshBasicMaterial color="#000" transparent opacity={0.35} /></mesh>
      {highlight && <mesh rotation-x={-Math.PI / 2} position={[0, 0.02, 0]}><ringGeometry args={[0.62, 0.78, 32]} /><meshBasicMaterial color="#479ef5" /></mesh>}
      <group position={[0, bob, 0]}>
        {[-1, 1].map((s) => (
          <group key={s} position={[0.12 * s, 0.92, 0]} rotation-x={swing * s}>
            <mesh position={[0, -0.27, 0]}><capsuleGeometry args={[0.085, 0.36, 4, 8]} /><meshStandardMaterial color={skinC} /></mesh>
            <mesh position={[0, -0.6, 0]}><capsuleGeometry args={[0.08, 0.26, 4, 8]} /><meshStandardMaterial color={socks} /></mesh>
            <mesh position={[0, -0.86, 0.06]}><boxGeometry args={[0.13, 0.08, 0.28]} /><meshStandardMaterial color="#0f172a" /></mesh>
          </group>
        ))}
        <mesh position={[0, 0.95, 0]}><boxGeometry args={[0.42, 0.24, 0.26]} /><meshStandardMaterial color={shorts} /></mesh>
        <mesh position={[0, 1.3, 0]}><capsuleGeometry args={[0.2, 0.34, 4, 12]} /><meshStandardMaterial color={shirt} emissive={highlight ? "#1e3a8a" : "#000"} emissiveIntensity={highlight ? 0.35 : 0} /></mesh>
        <mesh position={[0, 1.38, -0.205]}><planeGeometry args={[0.22, 0.2]} /><meshBasicMaterial color={gk ? "#0f172a" : kit.secondary} transparent opacity={0.85} side={THREE.DoubleSide} /></mesh>
        {[-1, 1].map((s) => (
          <group key={s} position={[0.27 * s, 1.5, 0]} rotation-x={-swing * s * 0.9} rotation-z={0.12 * s}>
            <mesh position={[0, -0.14, 0]}><capsuleGeometry args={[0.065, 0.16, 4, 8]} /><meshStandardMaterial color={shirt} /></mesh>
            <mesh position={[0, -0.36, 0]}><capsuleGeometry args={[0.055, 0.18, 4, 8]} /><meshStandardMaterial color={gk ? "#e5e7eb" : skinC} /></mesh>
          </group>
        ))}
        <mesh position={[0, 1.62, 0]}><cylinderGeometry args={[0.06, 0.07, 0.08, 10]} /><meshStandardMaterial color={skinC} /></mesh>
        <mesh position={[0, 1.79, 0]}><sphereGeometry args={[0.135, 18, 18]} /><meshStandardMaterial color={skinC} /></mesh>
        <mesh position={[0, 1.84, -0.01]}><sphereGeometry args={[0.14, 18, 18, 0, Math.PI * 2, 0, Math.PI / 2.2]} /><meshStandardMaterial color={hairC} roughness={0.9} /></mesh>
      </group>
      {(highlight || label) && <Html position={[0, 2.45, 0]} center distanceFactor={22} zIndexRange={[10, 0]}><span className="lens-tag"><b>{num}</b>{label ? ` ${label}` : ""}</span></Html>}
    </group>
  );
}

function shotPoint(rep: ReplayFull, k: number) {
  const a = rep.shot.from, b = rep.shot.to;
  return P(lerp(a.x, b.x, k), lerp(a.y, b.y, k) + Math.sin(Math.PI * k) * rep.shot.curve * 1.6, Math.max(0.11, lerp(0.11, b.z, k) + Math.sin(Math.PI * k) * (0.6 + b.z * 0.35)));
}

function Scene({ rep, time, view }: { rep: ReplayFull; time: number; view: View }) {
  const { camera } = useThree();
  const tl = useTimeline(rep);
  const camPos = useRef(new THREE.Vector3(0, 60, 40)), camLook = useRef(new THREE.Vector3());
  const frames = rep.frames, attackX = rep.shot.to.x, dirSign = attackX > 50 ? 1 : -1;
  const inBuild = time < tl.buildEnd;
  const segF = Math.min(tl.segs - 1e-6, time / PASS_S), si = Math.min(frames.length - 1, Math.floor(segF)), k = ease(segF - si);
  const fA = frames[si], fB = frames[Math.min(frames.length - 1, si + 1)];
  const shotK = inBuild ? 0 : Math.min(1, (time - tl.buildEnd) / SHOT_S);
  let ball: THREE.Vector3;
  if (inBuild) {
    const bt = fA.ball_to.x != null ? fA.ball_to : fB.ball;
    const dist = Math.hypot((bt.x as number) - fA.ball.x, (bt.y as number) - fA.ball.y);
    ball = P(lerp(fA.ball.x, bt.x as number, k), lerp(fA.ball.y, bt.y as number, k), 0.11 + Math.sin(Math.PI * k) * Math.min(3, dist / 12));
  } else ball = shotPoint(rep, ease(shotK));
  const last = frames[frames.length - 1].players;
  const players = (inBuild ? fA.players : last).map((p: PlayerPos) => {
    const q = (inBuild ? fB.players : last).find((x) => x.id === p.id) || p;
    const kk = inBuild ? k : 0, vx = (q.x - p.x) / PASS_S, vy = (q.y - p.y) / PASS_S, speed = inBuild ? Math.hypot(vx, vy) : 0.4;
    const toBall = Math.atan2(ball.x - (lerp(p.x, q.x, kk) - 52.5), ball.z - (lerp(p.y, q.y, kk) - 34));
    return { ...p, x: lerp(p.x, q.x, kk), y: lerp(p.y, q.y, kk), speed, heading: speed > 0.8 ? Math.atan2(vx, vy) : toBall };
  });
  const shooter = last.find((p) => p.id === rep.scorer) || { x: rep.shot.from.x, y: rep.shot.from.y };
  const highlights = new Set([rep.scorer, rep.assist, fA.actor, fA.receiver].filter(Boolean) as string[]);

  useFrame(() => {
    const tgtPos = new THREE.Vector3(), tgtLook = new THREE.Vector3();
    const goalCentre = P(attackX, 34, 1.2), shooterV = P(shooter.x, shooter.y, 0);
    const behind = shooterV.clone().add(new THREE.Vector3(-dirSign * 9, 3.2, (shooter.y - 34) * 0.12));
    const keeper = P(attackX - dirSign * 0.8, 34, 1.75);
    const overhead = () => { tgtPos.set(ball.x - dirSign * 6, 58, ball.z + 32); tgtLook.copy(ball); };
    const follow = () => { tgtPos.set(ball.x - dirSign * 20, 15, ball.z + 22); tgtLook.copy(ball); };
    if (view === "overhead") overhead();
    else if (inBuild && time < tl.buildEnd - PASS_S * 1.2) (view === "broadcast" ? follow() : overhead());
    else if (inBuild) { tgtPos.copy(behind); tgtLook.copy(goalCentre); }
    else if (view === "goalkeeper") { tgtPos.copy(keeper); tgtLook.copy(shooterV.clone().setY(1)); }
    else if (shotK < 1 || view === "behind_shooter") { tgtPos.copy(behind); tgtLook.copy(goalCentre); }
    else { tgtPos.copy(goalCentre.clone().add(new THREE.Vector3(-dirSign * 7, 0.8, 3))); tgtLook.copy(goalCentre.clone().add(new THREE.Vector3(dirSign, 0, 0))); }
    camPos.current.lerp(tgtPos, 0.07); camLook.current.lerp(tgtLook, 0.12);
    camera.position.copy(camPos.current); camera.lookAt(camLook.current);
  });

  const trails = frames.slice(0, inBuild ? si + 1 : frames.length - 1).map((f, i) => {
    const to = f.ball_to.x != null ? f.ball_to : frames[Math.min(frames.length - 1, i + 1)].ball;
    return { i, pts: [P(f.ball.x, f.ball.y, 0.06), P(to.x as number, to.y as number, 0.06)] };
  });
  const shotTrail = !inBuild ? Array.from({ length: 28 }, (_, i) => shotPoint(rep, (i / 27) * ease(shotK))) : null;
  return (
    <>
      <color attach="background" args={["#05070a"]} />
      <fog attach="fog" args={["#05070a", 70, 170]} />
      <hemisphereLight args={["#dbeafe", "#0b1d12", 0.55]} />
      <directionalLight position={[25, 60, 20]} intensity={1.25} />
      <directionalLight position={[-30, 40, -25]} intensity={0.35} color="#93c5fd" />
      <Stadium /><GoalGrid rep={rep} show={shotK >= 1} />
      {trails.map((tr) => (
        <group key={tr.i}>
          <Line points={tr.pts} color="#479ef5" lineWidth={3} />
          <Html position={tr.pts[0].clone().lerp(tr.pts[1], 0.5).setY(1.1)} center distanceFactor={26}><span className="lens-badge">{tr.i + 1}</span></Html>
        </group>
      ))}
      {shotTrail && <Line points={shotTrail} color="#f7c948" lineWidth={4} />}
      {players.map((p) => (
        <group key={p.id} position={P(p.x, p.y, 0)}>
          <Footballer kit={rep.teams[p.side]} gk={!!p.gk} skin={rep.looks?.[p.id]?.skin ?? 0} hair={rep.looks?.[p.id]?.hair ?? 0} heading={p.heading}
            phase={time * (5 + p.speed * 1.4) + p.num} speed={p.speed} highlight={highlights.has(p.id)} num={p.num}
            label={p.id === rep.scorer ? rep.scorer_name.split(" ").slice(-1)[0] : undefined} />
        </group>
      ))}
      <mesh position={ball}><sphereGeometry args={[0.24, 20, 20]} /><meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.35} /></mesh>
    </>
  );
}

export default function LunaLens({ matchId, replayId, view, setView, playKey }:
  { matchId: string; replayId: string | null; view: View; setView: (v: View) => void; playKey: number }) {
  const [rep, setRep] = useState<ReplayFull | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const tl = useTimeline(rep);
  const last = useRef<number | null>(null);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!replayId) return;
    setRep(null); setErr(null); setTime(0); setPlaying(!reduced);
    api.replay(matchId, replayId).then(setRep).catch((e) => setErr(String(e.message ?? e)));
  }, [matchId, replayId, reduced]);
  useEffect(() => { if (playKey) { setTime(0); setPlaying(true); } }, [playKey]);
  useEffect(() => {
    if (!playing || !rep) { last.current = null; return; }
    let raf = 0;
    const tick = (ts: number) => { if (last.current != null) setTime((t) => Math.min(tl.total, t + (ts - last.current!) / 1000)); last.current = ts; raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, rep, tl.total]);
  useEffect(() => { if (rep && time >= tl.total) setPlaying(false); }, [time, tl.total, rep]);

  if (!replayId) return <div className="lens lens-empty"><Target size={28} /><b>Luna Lens</b><p>Pick a goal on the moment rail, or say “show me the last goal from the keeper's view”.</p></div>;
  if (err) return <div className="lens lens-empty"><p>Replay unavailable: {err}</p></div>;
  if (!rep) return <div className="lens lens-empty"><div className="spinner" /><p>Reconstructing the move…</p></div>;

  const step = Math.min(rep.frames.length - 1, Math.floor(time / PASS_S)), f = rep.frames[step];
  const phase = time < tl.buildEnd ? "build" : time < tl.shotEnd ? "shot" : "goal";
  const facts = rep.summary_facts;
  const views: [View, string][] = [["broadcast", "Broadcast"], ["overhead", "Tactical"], ["behind_shooter", "Shooter"], ["goalkeeper", "Keeper"]];
  return (
    <div className="lens">
      <div className="lens-canvas" role="img" aria-label={`3D reconstruction of goal ${rep.goal_number} by ${rep.scorer_name}`}>
        <Canvas camera={{ fov: 42, position: [0, 60, 40] }} dpr={[1, 2]}><Scene rep={rep} time={time} view={view} /></Canvas>
        <div className="lens-hud-top">
          <span className="hud-chip"><span className="hud-dot" />GOAL {rep.goal_number} · {rep.clock} · {rep.team_name}</span>
          <div className="hud-steps" aria-hidden>
            {Array.from({ length: tl.segs }, (_, i) => <i key={i} className={time >= (i + 1) * PASS_S ? "done" : i === step && phase === "build" ? "now" : ""} />)}
            <i className={phase === "shot" ? "now shot" : phase === "goal" ? "done shot" : "shot"} />
          </div>
        </div>
        <div className="lens-hud-bottom" aria-live="polite">
          {phase === "build" && f && <><b>Pass {step + 1} of {tl.segs}</b><span>#{rep.numbers[f.actor] ?? "?"}{f.receiver ? ` → #${rep.numbers[f.receiver] ?? "?"}` : ""}</span></>}
          {phase === "shot" && <><b>Shot</b><span>{rep.scorer_name} · {facts.shot_speed_kmh} km/h</span></>}
          {phase === "goal" && <><b className="goal-word">GOAL</b><span>{rep.scorer_name} · {String(facts.target).replace("-", " ")} corner · {rep.score_after.home}–{rep.score_after.away}</span></>}
        </div>
      </div>
      <div className="lens-bar">
        <button className="icon-btn primary" onClick={() => { if (time >= tl.total) setTime(0); setPlaying(!playing); }} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? <Pause size={18} /> : <Play size={18} />}</button>
        <button className="icon-btn" onClick={() => { setTime(0); setPlaying(true); }} aria-label="Restart replay"><RotateCcw size={16} /></button>
        <input type="range" min={0} max={tl.total} step={0.01} value={time} aria-label="Scrub replay" className="scrub" onChange={(e) => { setTime(parseFloat(e.target.value)); setPlaying(false); }} />
        <div className="segmented small" role="tablist" aria-label="Camera">
          <Camera size={14} aria-hidden />
          {views.map(([v, l]) => <button key={v} role="tab" aria-selected={view === v} className={view === v ? "on" : ""} onClick={() => { setView(v); setTime(0); setPlaying(true); }}>{l}</button>)}
        </div>
      </div>
      <div className="lens-facts">
        <span><Users size={14} /><b>{facts.passes}</b> passes · <b>{facts.players_involved}</b> players</span>
        <span><Timer size={14} /><b>{facts.duration_s}s</b> build-up</span>
        <span><Gauge size={14} /><b>{facts.xg}</b> xG</span>
        <span><Target size={14} />{String(facts.target).replace("-", " ")}</span>
        {rep.assist_name && rep.assist_name !== "Unknown" && <span>Assist <b>{rep.assist_name}</b></span>}
      </div>
    </div>
  );
}
