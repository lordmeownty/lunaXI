import { ArrowRight, AudioLines, BadgeCheck, Eye, PlayCircle, ShieldCheck, Sparkles, Tv } from "lucide-react";
import { useEffect, useState } from "react";
import Brand from "../components/Brand";
import Crest from "../components/Crest";
import UserMenu from "../components/UserMenu";
import { api } from "../lib/api";
import { ROLE_LABEL, useAuth } from "../lib/auth";
import type { MatchIndexItem } from "../lib/types";

const ART = ["art-a", "art-b", "art-c", "art-d", "art-e"];
const KIND = ["Comeback", "Tactical masterclass", "Seven-goal thriller", "Underdog story", "Controversial finish"];
const ROLE_PITCH: Record<string, string> = {
  "Luna.Director": "Everything in one place: watch, ask, verify, approve and operate.",
  "Luna.Fan": "Ask anything by voice, catch up in seconds and watch any goal rebuilt in 3D.",
  "Luna.Analyst": "Get evidence-backed tactical explanations with before/after numbers.",
  "Luna.Broadcaster": "Verify commentary and build recap packages for editorial approval.",
  "Luna.Editor": "Review and approve what goes on air, with a full audit trail.",
  "Luna.Admin": "Operate agents, cost, safety and Azure event pipelines.",
};

export default function Home({ open }: { open: (id: string) => void }) {
  const { me } = useAuth();
  const [matches, setMatches] = useState<MatchIndexItem[]>([]);
  const [health, setHealth] = useState<{ mode: string } | null>(null);
  const [featured, setFeatured] = useState(2);
  useEffect(() => { api.matches().then(setMatches).catch(() => {}); api.health().then(setHealth).catch(() => {}); }, [me?.primary_role]);
  const hero = matches[featured];
  return (
    <div className="home">
      <header className="topbar">
        <Brand />
        <nav aria-label="Primary"><a href="#matches">Matches</a><a href="#how">How it works</a><a href="#trust">Trust</a></nav>
        <div className="row"><span className={`status ${health?.mode === "foundry" ? "ok" : "warn"}`}><i className="dot" />{health?.mode === "foundry" ? "Foundry connected" : "Offline demo"}</span><UserMenu /></div>
      </header>
      <section className={`hero ${ART[featured]}`}>
        <div className="hero-copy">
          <span className="eyebrow">Welcome back{me ? `, ${me.name.split(" ")[0]}` : ""} · {me ? ROLE_LABEL[me.primary_role] : ""}</span>
          <h1>Every match has<br /><em>a story behind it.</em></h1>
          <p>{me ? ROLE_PITCH[me.primary_role] : ""}</p>
          <div className="row">
            <button className="btn primary lg" onClick={() => hero && open(hero.id)}><PlayCircle size={20} />Open featured match</button>
            <a className="btn lg glass" href="#how"><Eye size={18} />How it works</a>
          </div>
          <span className="trust"><ShieldCheck size={15} />100% synthetic data · every claim traceable to an event</span>
        </div>
        {hero && (
          <div className="hero-card">
            <span className="eyebrow">FEATURED · {hero.venue.toUpperCase()}</span>
            <div className="fixture">
              <div><Crest colour={hero.home.colour} short={hero.home.short} size={52} /><b>{hero.home.name}</b></div>
              <strong>{hero.final_score.home}<i>:</i>{hero.final_score.away}</strong>
              <div><Crest colour={hero.away.colour} short={hero.away.short} size={52} /><b>{hero.away.name}</b></div>
            </div>
            <h3>{hero.title}</h3><p>{hero.subtitle}</p>
            <div className="tags">{hero.showcase.map((s) => <span key={s}>{s}</span>)}</div>
          </div>
        )}
        <div className="hero-dots">{matches.map((m, i) => <button key={m.id} aria-label={`Feature ${m.title}`} className={featured === i ? "on" : ""} onClick={() => setFeatured(i)} />)}</div>
      </section>
      <section className="section" id="matches">
        <div className="section-head"><div><span className="eyebrow">FIVE STORIES</span><h2>Choose your match</h2></div><p className="muted">Each fixture is designed to show a different side of football intelligence.</p></div>
        <div className="match-grid">
          {matches.map((m, i) => (
            <article key={m.id} className={`match-card ${ART[i]}`}>
              <button className="hit" onClick={() => open(m.id)} aria-label={`Open ${m.title}`} />
              <div className="mc-top"><span>{String(i + 1).padStart(2, "0")} · {KIND[i]}</span><span className="badge"><BadgeCheck size={13} />Synthetic</span></div>
              <div className="mc-fixture"><span><Crest colour={m.home.colour} short={m.home.short} size={30} />{m.home.short}</span><strong>{m.final_score.home} – {m.final_score.away}</strong><span>{m.away.short}<Crest colour={m.away.colour} short={m.away.short} size={30} /></span></div>
              <h3>{m.title}</h3><p>{m.subtitle}</p>
              <div className="mc-foot"><span>{m.replays} 3D replays · {m.events.toLocaleString()} events</span><span className="go">Open <ArrowRight size={15} /></span></div>
            </article>
          ))}
        </div>
      </section>
      <section className="section how" id="how">
        <div><span className="eyebrow">ONE MATCH · ONE CONNECTED EXPERIENCE</span><h2>Watch it. Ask it.<br />Prove it.</h2></div>
        <div className="how-list">
          <div><span className="ico"><Tv size={20} /></span><div><h3>Live story & moments</h3><p>Every goal, card, change and momentum shift on one rail. Select a moment and everything follows it.</p></div></div>
          <div><span className="ico"><AudioLines size={20} /></span><div><h3>Talk to the match</h3><p>GPT Realtime voice. Ask questions or give commands; Luna routes each request to the cheapest reliable path.</p></div></div>
          <div><span className="ico"><Sparkles size={20} /></span><div><h3>Visual proof</h3><p>Luna Lens rebuilds the move in 3D: every pass, the shot and where it went in.</p></div></div>
        </div>
      </section>
      <section className="section trust-block" id="trust">
        <div className="card trust-card"><ShieldCheck size={26} /><h3>Trusted by design</h3>
          <p className="muted">Fictional clubs and players; outcomes simulated with Open Football (Apache-2.0) at build time; numbers computed deterministically; every AI claim checked by the Evidence Referee; Microsoft sign-in, Key Vault, audit trail and editorial approval for anything that goes on air.</p>
          <div className="flow"><span>Open Football engine</span><ArrowRight size={14} /><span>Fictional match packages</span><ArrowRight size={14} /><span>Luna XI agents</span><ArrowRight size={14} /><span>Verified experience</span></div></div>
      </section>
      <footer className="foot"><Brand compact /><span className="muted">Every match is fictional. Every insight is explainable.</span></footer>
    </div>
  );
}
