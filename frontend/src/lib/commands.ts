/** Local voice/text command parser: app actions run instantly without a model; questions go to Luna. */
import type { Command } from "./types";

const SECTIONS: Record<string, string> = { match: "match", game: "match", recap: "recaps", recaps: "recaps", studio: "studio", broadcast: "studio",
  approval: "approvals", approvals: "approvals", operation: "operations", operations: "operations", ops: "operations", system: "operations" };
const VIEWS: Record<string, string> = { keeper: "goalkeeper", goalkeeper: "goalkeeper", overhead: "overhead", tactical: "overhead", top: "overhead",
  shooter: "behind_shooter", behind: "behind_shooter", broadcast: "broadcast", tv: "broadcast" };
const AUD: Record<string, string> = { simple: "new_fan", simply: "new_fan", beginner: "new_fan", tactical: "tactical", analyst: "tactical",
  broadcaster: "broadcaster", presenter: "broadcaster", fan: "fan", audio: "accessible", accessible: "accessible" };

export function parseCommand(raw: string): Command | null {
  const t = raw.toLowerCase().replace(/[.!?,]/g, " ").replace(/\s+/g, " ").trim().replace(/^(hey |ok |okay )?luna /, "");
  if (/^(play|resume|start|kick ?off|start the match|play the match)$/.test(t)) return { action: "play" };
  if (/^(pause|stop|hold on|wait)$/.test(t)) return { action: "pause" };
  if (/^(restart|start again|from the start|rewind)( the match)?$/.test(t)) return { action: "restart" };
  if (/^(next|next moment|next event|skip)$/.test(t)) return { action: "next_moment" };
  if (/^(previous|back|previous moment|go back)$/.test(t)) return { action: "previous_moment" };
  let m = t.match(/^(?:open|go to|show|switch to|take me to) (?:the )?(match|game|recaps?|studio|broadcast|approvals?|operations?|ops|system)(?: page| tab| view)?$/);
  if (m) return { action: "open_section", value: SECTIONS[m[1]] };
  m = t.match(/(?:speed|faster|slower).*?(600|240|60)|^(600|240|60)x?$/);
  if (m) return { action: "set_speed", value: m[1] ?? m[2] };
  m = t.match(/^(?:switch to |change to |use )?(?:the )?(keeper|goalkeeper|overhead|tactical|top|shooter|behind|broadcast|tv) (?:view|camera|angle)$/);
  if (m) return { action: "set_view", value: VIEWS[m[1]] };
  m = t.match(/^(?:explain|talk|speak) (?:it )?(?:like (?:a |an )?)?(simple|simply|beginner|tactical|analyst|broadcaster|presenter|fan|audio|accessible)/);
  if (m) return { action: "set_audience", value: AUD[m[1]] };
  m = t.match(/^(?:open|switch to|load|go to) (?:the )?(.+?) match$/);
  if (m) return { action: "open_match", value: m[1] };
  return null;
}
