import type { AskResponse, Audience, MatchIndexItem, MatchSummary, Me, Package, RecapPackage, ReplayFull, View } from "./types";

const BASE = ((import.meta.env as any).VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
let authProvider: () => Promise<Record<string, string>> = async () => ({});
export function setAuthProvider(fn: () => Promise<Record<string, string>>) { authProvider = fn; }
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(await authProvider()), ...(init?.headers || {}) } });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* ignore */ }
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json() as Promise<T>;
}
const post = <T,>(p: string, body: any) => j<T>(p, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => r.json()) as Promise<{ mode: string; auth: string; foundry: boolean; orchestrator: string }>,
  me: () => j<Me>("/api/me"),
  sessionEvent: (kind: "sign_in" | "sign_out" | "view_as", value?: string) => post("/api/session/event", { kind, value }).catch(() => null),
  matches: () => j<MatchIndexItem[]>("/api/matches"),
  match: (id: string) => j<MatchSummary>(`/api/matches/${id}`),
  stats: (id: string, t?: number | null) => j<any>(`/api/matches/${id}/stats${t != null ? `?t_to=${t}` : ""}`),
  replay: (id: string, rid: string) => j<ReplayFull>(`/api/matches/${id}/replays/${rid}`),
  streamUrl: async (id: string, speed: number, start = 0) => {
    const { ticket } = await post<{ ticket: string }>(`/api/matches/${id}/stream-ticket`, {});
    return `${BASE}/api/matches/${id}/stream?ticket=${encodeURIComponent(ticket)}&speed=${speed}&start_t=${start}`;
  },
  ask: (match_id: string, question: string, audience: Audience, playback_t: number | null, focus_moment_id?: string | null, goal_number?: number, view?: View) =>
    post<AskResponse>("/api/ask", { match_id, question, audience, playback_t, focus_moment_id, goal_number, view }),
  recap: (match_id: string, audience: Audience, phase: "half" | "full" | "live", playback_t: number | null) => post<RecapPackage>("/api/recap", { match_id, audience, phase, playback_t }),
  poster: (match_id: string) => post<{ b64?: string; url?: string; prompt: string; label: string }>("/api/recap/poster", { match_id }),
  realtimeSession: (match_id: string) => post<{ client_secret: string; webrtc_url: string; model: string; session: any }>("/api/realtime/session", { match_id }),
  sampleCommentary: (id: string) => j<{ lines: { speaker: string; t_match: number; text: string }[] }>(`/api/studio/${id}/sample-commentary`),
  verify: (match_id: string, lines: any[]) => post<any>("/api/studio/verify", { match_id, lines }),
  transcribe: async (match_id: string, file: File) => {
    const fd = new FormData(); fd.append("match_id", match_id); fd.append("file", file);
    const r = await fetch(`${BASE}/api/studio/transcribe`, { method: "POST", body: fd, headers: await authProvider() });
    if (!r.ok) throw new ApiError(r.status, (await r.text()).slice(0, 300));
    return r.json();
  },
  submitPackage: (match_id: string, title: string, playback_t: number | null) => post<Package>("/api/packages", { match_id, title, audience: "broadcaster", phase: playback_t != null ? "live" : "full", playback_t }),
  packages: () => j<Package[]>("/api/packages"),
  decide: (id: string, approve: boolean, note: string) => post<Package>(`/api/packages/${id}/decision`, { approve, note }),
  controlRoom: () => j<any>("/api/control-room"),
  workflow: () => j<any>("/api/agents/workflow"),
  audit: () => j<any>("/api/audit?limit=60"),
  publishEvents: (id: string) => post<any>(`/api/ops/matches/${id}/publish-events`, {}),
};
