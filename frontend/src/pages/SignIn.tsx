import { ArrowRight, ChevronDown, KeyRound, Lock, ScrollText, ShieldCheck } from "lucide-react";
import { useState } from "react";
import Brand from "../components/Brand";
import { ROLE_BLURB, ROLE_LABEL, useAuth } from "../lib/auth";
import type { Role } from "../lib/types";

function MicrosoftLogo() {
  return <svg width="20" height="20" viewBox="0 0 21 21" aria-hidden><rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect x="1" y="11" width="9" height="9" fill="#00a4ef" /><rect x="11" y="11" width="9" height="9" fill="#ffb900" /></svg>;
}

export default function SignIn() {
  const { signIn, entra, error } = useAuth();
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const go = async (r?: Role) => { setBusy(true); await new Promise((res) => setTimeout(res, entra ? 0 : 650)); await signIn(r); };
  return (
    <main className="signin">
      <section className="signin-art" aria-hidden>
        <div className="art-pitch"><i /><i /><i /></div>
        <div className="art-copy"><span className="eyebrow">INSIDE THE GAME</span><h1>Football,<br /><em>understood.</em></h1>
          <p>Explainable match intelligence, live narratives and verified recaps, built on Microsoft Foundry and Azure.</p></div>
      </section>
      <section className="signin-panel">
        <Brand />
        <h2>Sign in</h2>
        <p className="muted">Use your work account to continue to Luna XI.</p>
        <button className="btn ms block" onClick={() => go()} disabled={busy}><MicrosoftLogo />{busy ? "Signing you in…" : "Sign in with Microsoft"}</button>
        <ul className="signin-points">
          <li><ShieldCheck size={16} />Microsoft Entra ID single sign-on with role-based access</li>
          <li><KeyRound size={16} />Secrets stored in Azure Key Vault, accessed by managed identity</li>
          <li><ScrollText size={16} />Every sign-in, approval and role switch is written to a tamper-evident audit log</li>
          <li><Lock size={16} />Nothing reaches air without an editor's approval</li>
        </ul>
        {!entra && <p className="demo-note">Demo sign-in: you'll be signed in as <b>Director</b> (sees everything, can preview any role). Real Entra ID can be switched on in configuration.</p>}
        {!entra && <button className="link more" onClick={() => setMore(!more)}>Sign in as a specific role <ChevronDown size={14} /></button>}
        {more && <div className="personas">{(["Luna.Fan", "Luna.Analyst", "Luna.Broadcaster", "Luna.Editor", "Luna.Admin"] as Role[]).map((r) => (
          <button key={r} className="persona" onClick={() => go(r)}><span className="avatar">{ROLE_LABEL[r][0]}</span><div><b>{ROLE_LABEL[r]}</b><p>{ROLE_BLURB[r]}</p></div><ArrowRight size={16} /></button>))}</div>}
        {error && <p className="notice bad">{error}</p>}
        <p className="legal muted small">All teams, players and matches are fictional. No real Premier League data is used.</p>
      </section>
    </main>
  );
}
