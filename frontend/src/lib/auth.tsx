/**
 * Sign-in. Default: the "Sign in with Microsoft" button performs a SIMULATED sign-in (clearly labelled) and signs you in
 * as Luna.Director, who can see everything and preview any role with "View as". If VITE_ENTRA_CLIENT_ID is set, the same
 * button uses real Microsoft Entra ID (MSAL, auth code + PKCE).
 */
import { PublicClientApplication, type AccountInfo } from "@azure/msal-browser";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setAuthProvider } from "./api";
import type { Me, Role } from "./types";

const env = import.meta.env as Record<string, string | undefined>;
const CLIENT_ID = env.VITE_ENTRA_CLIENT_ID || "";
const SCOPE = env.VITE_ENTRA_API_SCOPE || (CLIENT_ID ? `api://${CLIENT_ID}/access_as_user` : "");
export const ENTRA_ENABLED = Boolean(CLIENT_ID);
const msal = ENTRA_ENABLED ? new PublicClientApplication({
  auth: { clientId: CLIENT_ID, authority: `https://login.microsoftonline.com/${env.VITE_ENTRA_TENANT_ID || "organizations"}`, redirectUri: window.location.origin },
  cache: { cacheLocation: "sessionStorage" } }) : null;

export const ROLE_LABEL: Record<string, string> = { "Luna.Fan": "Fan", "Luna.Analyst": "Analyst", "Luna.Broadcaster": "Broadcaster", "Luna.Editor": "Editor", "Luna.Admin": "Admin", "Luna.Director": "Director" };
export const ROLE_BLURB: Record<string, string> = {
  "Luna.Director": "Everything: match, recaps, studio, approvals, operations. Can preview any role.",
  "Luna.Fan": "Second-screen companion, voice, catch-me-up, accessible audio.",
  "Luna.Analyst": "Deep tactical explanations powered by the reasoning model.",
  "Luna.Broadcaster": "Verify commentary, build packages, submit for approval.",
  "Luna.Editor": "Approve what goes on air. Separation of duties enforced.",
  "Luna.Admin": "Agents, cost, safety, audit and Azure event pipelines.",
};

interface AuthCtx { me: Me | null; ready: boolean; error: string | null; entra: boolean; signIn: (role?: Role) => Promise<void>; signOut: () => void; can: (cap: string) => boolean; viewAs: Role | null; setViewAs: (r: Role | null) => void; refresh: () => void }
const Ctx = createContext<AuthCtx>({} as AuthCtx);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [demoRole, setDemoRole] = useState<Role | null>(() => (sessionStorage.getItem("luna.role") as Role) || null);
  const [viewAs, setViewAsState] = useState<Role | null>(() => (sessionStorage.getItem("luna.viewAs") as Role) || null);
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(!ENTRA_ENABLED);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!msal) return;
    (async () => {
      try {
        await msal.initialize();
        const res = await msal.handleRedirectPromise();
        const acct = res?.account ?? msal.getAllAccounts()[0] ?? null;
        if (acct) { msal.setActiveAccount(acct); setAccount(acct); }
      } catch (e: any) { setError(e?.message ?? String(e)); }
      setReady(true);
    })();
  }, []);

  const headers = useCallback(async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = viewAs ? { "X-View-As": viewAs } : {};
    if (ENTRA_ENABLED && account) return { ...h, Authorization: `Bearer ${(await msal!.acquireTokenSilent({ scopes: [SCOPE], account })).accessToken}` };
    if (demoRole) return { ...h, "X-Demo-Role": demoRole };
    return h;
  }, [account, demoRole, viewAs]);

  useEffect(() => {
    if (!(account || demoRole)) { setMe(null); return; }
    setAuthProvider(headers);
    api.me().then(setMe).catch((e) => setError(String(e.message ?? e)));
  }, [headers, account, demoRole, tick]);

  const value = useMemo<AuthCtx>(() => ({
    me, ready, error, entra: ENTRA_ENABLED, viewAs,
    signIn: async (role: Role = "Luna.Director") => {
      setError(null);
      if (msal) { await msal.loginRedirect({ scopes: [SCOPE], prompt: "select_account" }); return; }
      sessionStorage.setItem("luna.role", role); setDemoRole(role);
      setAuthProvider(async () => ({ "X-Demo-Role": role }));
      api.sessionEvent("sign_in", role);
    },
    signOut: () => {
      api.sessionEvent("sign_out");
      setMe(null); sessionStorage.removeItem("luna.role"); sessionStorage.removeItem("luna.viewAs"); setViewAsState(null);
      if (msal && account) msal.logoutRedirect({ account }); else setDemoRole(null);
    },
    setViewAs: (r: Role | null) => {
      if (r) sessionStorage.setItem("luna.viewAs", r); else sessionStorage.removeItem("luna.viewAs");
      setViewAsState(r);
      api.sessionEvent("view_as", r ?? "Luna.Director");
    },
    can: (cap: string) => Boolean(me?.capabilities.includes(cap)),
    refresh: () => setTick((x) => x + 1),
  }), [me, ready, error, account, viewAs]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
