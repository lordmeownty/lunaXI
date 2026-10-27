"""Agent traces + measured efficiency (+ optional Azure Monitor OpenTelemetry export)."""
from __future__ import annotations

import logging
import time
import uuid
from collections import Counter, deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from .config import settings

log = logging.getLogger("luna.telemetry")
try:
    from opentelemetry import trace as _otel
    _tracer = _otel.get_tracer("luna-xi")
except Exception:  # pragma: no cover
    _tracer = None


def configure_azure_monitor() -> bool:
    if not settings.appinsights_connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor as _cfg
        _cfg(connection_string=settings.appinsights_connection_string)
        return True
    except Exception as e:  # pragma: no cover
        log.warning("Azure Monitor not configured: %s", e)
        return False


@dataclass
class TraceStep:
    agent: str
    action: str
    status: str = "ok"
    model: str | None = None
    source: str | None = None
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    detail: dict = field(default_factory=dict)


@dataclass
class Trace:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    engine: str = "builtin"
    steps: list[TraceStep] = field(default_factory=list)

    @contextmanager
    def step(self, agent: str, action: str, **detail):
        st = TraceStep(agent=agent, action=action, detail=dict(detail))
        t0 = time.perf_counter()
        cm = _tracer.start_as_current_span(f"{agent}.{action}") if _tracer else None
        span = cm.__enter__() if cm else None
        try:
            yield st
        except Exception as e:
            st.status = "error"
            st.detail["error"] = str(e)[:300]
            raise
        finally:
            st.latency_ms = st.latency_ms or int((time.perf_counter() - t0) * 1000)
            self.steps.append(st)
            if span is not None:
                span.set_attribute("gen_ai.agent.name", agent)
                span.set_attribute("luna.status", st.status)
                if st.model:
                    span.set_attribute("gen_ai.request.model", st.model)
                span.set_attribute("gen_ai.usage.input_tokens", st.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", st.output_tokens)
                cm.__exit__(None, None, None)

    def to_dict(self) -> dict:
        return {"id": self.id, "engine": self.engine, "steps": [asdict(s) for s in self.steps], "total_ms": sum(s.latency_ms for s in self.steps)}


class Efficiency:
    def __init__(self):
        self.requests = self.advanced_calls = self.fast_calls = 0
        self.by_tier: Counter = Counter()
        self.tokens: Counter = Counter()
        self.cost_usd = 0.0
        self.latencies: deque = deque(maxlen=500)
        self.reason_seen: deque = deque(maxlen=100)
        self.fallbacks = self.retries = self.rejections = 0

    def record(self, tier: str, trace: Trace, total_ms: int):
        from .platform.governance import budget
        self.requests += 1
        self.by_tier[tier] += 1
        self.latencies.append(total_ms)
        for s in trace.steps:
            self.fallbacks += s.status == "fallback"
            self.rejections += s.status == "rejected"
            self.retries += "retry" in s.action
            if s.model and s.input_tokens + s.output_tokens > 0:
                if s.model == settings.reasoning_deployment:
                    self.advanced_calls += 1
                    self.reason_seen.append((s.input_tokens, s.output_tokens))
                    cost = (s.input_tokens * settings.price_reason_in + s.output_tokens * settings.price_reason_out) / 1e6
                else:
                    self.fast_calls += 1
                    cost = (s.input_tokens * settings.price_fast_in + s.output_tokens * settings.price_fast_out) / 1e6
                self.cost_usd += cost
                budget.add(cost)
                self.tokens["input"] += s.input_tokens
                self.tokens["output"] += s.output_tokens

    def snapshot(self) -> dict:
        ai, ao = ((sum(a for a, _ in self.reason_seen) / len(self.reason_seen), sum(b for _, b in self.reason_seen) / len(self.reason_seen))
                  if self.reason_seen else (2500.0, 350.0))
        baseline = self.requests * (ai * settings.price_reason_in + ao * settings.price_reason_out) / 1e6
        lat = sorted(self.latencies)
        return {"requests": self.requests, "by_tier": dict(self.by_tier), "advanced_model_calls": self.advanced_calls,
                "fast_model_calls": self.fast_calls, "advanced_calls_avoided": max(0, self.requests - self.advanced_calls),
                "tokens": dict(self.tokens), "measured_cost_usd": round(self.cost_usd, 5), "baseline_cost_usd_estimate": round(baseline, 5),
                "estimated_saving_usd": round(max(0, baseline - self.cost_usd), 5), "fallbacks": self.fallbacks,
                "retries": self.retries, "referee_rejections": self.rejections,
                "p50_ms": lat[len(lat) // 2] if lat else 0, "p95_ms": lat[max(0, int(len(lat) * 0.95) - 1)] if lat else 0,
                "assumption": "Baseline = every request sent to the reasoning model; average tokens measured once available."}


efficiency = Efficiency()
recent_traces: deque = deque(maxlen=50)
