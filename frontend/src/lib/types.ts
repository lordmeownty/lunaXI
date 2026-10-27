export type Audience = "fan" | "new_fan" | "tactical" | "broadcaster" | "accessible";
export type View = "broadcast" | "overhead" | "behind_shooter" | "goalkeeper";
export type Role = "Luna.Fan" | "Luna.Analyst" | "Luna.Broadcaster" | "Luna.Editor" | "Luna.Admin" | "Luna.Director";
export type Surface = "match" | "recaps" | "studio" | "approvals" | "operations";

export interface Me { oid: string; name: string; email: string; roles: Role[]; real_roles: Role[]; primary_role: Role; viewing_as: Role | null; can_preview: boolean; previewable_roles: Role[]; tenant: string; auth: "entra" | "demo"; capabilities: string[]; auth_mode: string; pending_approvals: number }
export interface TeamLite { id: string; name: string; short: string; colour: string; kit_secondary?: string; gk_colour?: string; formation_start?: string }
export interface MatchIndexItem { id: string; title: string; subtitle: string; venue: string; home: TeamLite; away: TeamLite; final_score: { home: number; away: number }; showcase: string[]; events: number; replays: number }
export interface KeyMoment { id: string; type: string; minute: number; clock: string; team: string; player: string | null; headline: string; replay_id?: string; score?: { home: number; away: number }; event_ids: string[] }
export interface ReplayLite { id: string; goal_number: number; clock: string; minute: number; team: string; scorer: string; title: string; summary_facts: Record<string, any>; goal_event_id?: string }
export interface MatchSummary {
  id: string; title: string; subtitle: string; venue: string; final_score: { home: number; away: number }; story: string;
  home: TeamLite; away: TeamLite; key_moments: KeyMoment[]; replays: ReplayLite[]; duration_s: number;
  goals: { n: number; clock: string; minute: number; team: string; scorer_name: string; build_up_passes: number }[];
  players: Record<string, { name: string; number: number; role: string; team_name: string; side: string }>; provenance: Record<string, any>; showcase: string[];
}
export interface TraceStep { agent: string; action: string; status: string; model?: string | null; source?: string | null; latency_ms: number; input_tokens: number; output_tokens: number; detail: Record<string, any> }
export interface Trace { id: string; engine?: string; steps: TraceStep[]; total_ms: number }
export interface Evidence { label: string; value: any; event_ids: string[]; kind: string }
export interface AskAction { type: "open_replay" | "suggest_replay"; replay_id: string; goal_number?: number; view?: View }
export interface AskResponse { answer: string; audience: Audience; intent: string; tier: string; decision: Record<string, any>; evidence: Evidence[]; verification: Record<string, any>; action: AskAction | null; trace: Trace; latency_ms: number; clock?: string; focus?: any; package?: RecapPackage }
export interface RecapPackage { phase: string; audience: Audience; recap: string; score: { home: number; away: number }; talking_points: string[]; top_players: { name: string; team: string; impact: number }[]; replay_reel: { id: string; goal_number: number; clock: string; title: string }[]; stats: Record<string, any>; verification: Record<string, any>; poster_prompt: string; requires_editor_approval: boolean; trace?: Trace }
export interface PlayerPos { id: string; num: number; side: "home" | "away"; gk?: boolean; x: number; y: number }
export interface Frame { t: number; event_id: string; action: string; actor: string; receiver: string | null; ball: { x: number; y: number; z: number }; ball_to: { x: number | null; y: number | null; z: number }; players: PlayerPos[] }
export interface Kit { colour: string; secondary: string; gk: string; name: string; short: string }
export interface ReplayFull extends ReplayLite { side: "home" | "away"; assist: string | null; frames: Frame[]; shot: { from: { x: number; y: number; z: number }; to: { x: number; y: number; z: number }; curve: number }; score_after: { home: number; away: number }; scorer_name: string; assist_name: string; team_name: string; teams: { home: Kit; away: Kit }; numbers: Record<string, number>; looks: Record<string, { skin: number; hair: number }>; event_ids: string[] }
export interface Claim { line: number; claim: string; type: string; value: string; speaker?: string; verdict: "supported" | "misleading" | "unverifiable"; proof: string; event_ids: string[] }
export interface Package { id: string; match_id: string; audience: Audience; title: string; status: "pending_review" | "approved" | "changes_requested"; recap: string; talking_points: string[]; verification: any; submitted_by: string; submitted_at: string; decided_by?: string; note?: string; history: { at: string; by: string; action: string; note?: string }[]; event?: { mode: string } }
export interface Command { action: "play" | "pause" | "restart" | "next_moment" | "previous_moment" | "open_match" | "open_section" | "set_speed" | "set_view" | "set_audience"; value?: string }
