import { AlertTriangle, CheckCircle2, CornerDownRight, MinusCircle, RotateCw, ShieldX } from "lucide-react";
import type { Trace } from "../lib/types";

const ICON: Record<string, any> = { ok: CheckCircle2, fallback: CornerDownRight, rejected: ShieldX, retry: RotateCw, skipped: MinusCircle, error: AlertTriangle };
export default function TraceView({ trace }: { trace: Trace }) {
  return (
    <ol className="trace" aria-label="Agent trace">
      {trace.steps.map((s, i) => {
        const I = ICON[s.status] ?? CheckCircle2;
        return (
          <li key={i} className={`st-${s.status}`}>
            <I size={13} aria-label={s.status} /><span className="t-agent">{s.agent}</span><span className="t-act">{s.action.replace(/_/g, " ")}</span>
            <span className="t-meta">{s.model ?? s.source ?? "deterministic"}{s.input_tokens + s.output_tokens > 0 ? ` · ${s.input_tokens + s.output_tokens} tok` : ""} · {s.latency_ms}ms</span>
          </li>
        );
      })}
      <li className="t-total">{trace.steps.length} steps · {trace.total_ms} ms · engine {trace.engine ?? "builtin"} · trace {trace.id}</li>
    </ol>
  );
}
