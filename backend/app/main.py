"""Luna XI API: FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agents.orchestrator import active_engine
from .config import settings
from .data.store import get_store
from .routers import a2a, enterprise, intelligence, matches
from .security.guard import SecurityHeadersMiddleware
from .telemetry import configure_azure_monitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await enterprise.seed_demo_package()
    yield


app = FastAPI(title="Luna XI API", version="1.2.0", lifespan=lifespan,
              description="Explainable, voice-first football match intelligence on synthetic data.")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type", "X-Demo-Role", "X-View-As"])
for r in (matches.router, intelligence.router, enterprise.router, a2a.router):
    app.include_router(r)

if configure_azure_monitor():
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # pragma: no cover
        pass


@app.get("/health")
def health():
    return {"status": "ok", "matches": len(get_store().index), "foundry": settings.foundry_enabled,
            "mode": "foundry" if settings.foundry_enabled else "offline-deterministic", "auth": settings.auth_mode,
            "orchestrator": active_engine()}


@app.get("/")
def root():
    return {"name": "Luna XI", "docs": "/docs", "health": "/health", "agent_card": "/.well-known/agent.json"}
