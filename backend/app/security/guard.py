"""Runtime protection: security headers, per-user rate limiting, Prompt Shields / moderation."""
from __future__ import annotations

import re
import time
from collections import defaultdict

import httpx
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings

SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin",
                    "Permissions-Policy": "microphone=(self), camera=()", "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                    "Cache-Control": "no-store"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            if not (k == "Cache-Control" and request.url.path.endswith("/stream")):
                response.headers.setdefault(k, v)
        return response


class RateLimiter:
    def __init__(self):
        self.state: dict[tuple[str, str], tuple[float, float]] = defaultdict(lambda: (settings.rate_limit_per_min, time.time()))

    def check(self, who: str, bucket: str, per_min: float | None = None):
        cap = per_min or settings.rate_limit_per_min
        tokens, last = self.state[(who, bucket)]
        now = time.time()
        tokens = min(cap, tokens + (now - last) * cap / 60.0)
        if tokens < 1:
            raise HTTPException(429, "Too many requests, please slow down", headers={"Retry-After": "5"})
        self.state[(who, bucket)] = (tokens - 1, now)


limiter = RateLimiter()
INJECTION_PATTERNS = [r"ignore (all|any|the|previous|prior) (instructions|rules)", r"system prompt", r"you are now", r"developer mode",
                      r"reveal (your|the) (prompt|instructions|key)", r"api[- ]?key", r"<\s*script", r"disregard (the|your) (rules|instructions)"]


async def screen_text(text: str) -> dict:
    result = {"blocked": False, "reasons": [], "source": "local rules"}
    for pat in INJECTION_PATTERNS:
        if re.search(pat, text, re.I):
            result["blocked"] = True
            result["reasons"].append("prompt_injection_pattern")
            break
    if settings.content_safety_endpoint and settings.content_safety_key:
        headers, base = {"Ocp-Apim-Subscription-Key": settings.content_safety_key}, settings.content_safety_endpoint
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                shield = await c.post(f"{base}/contentsafety/text:shieldPrompt?api-version=2024-09-01", headers=headers,
                                      json={"userPrompt": text[:10000], "documents": []})
                if shield.status_code == 200 and shield.json().get("userPromptAnalysis", {}).get("attackDetected"):
                    result["blocked"] = True
                    result["reasons"].append("prompt_shield_attack")
                mod = await c.post(f"{base}/contentsafety/text:analyze?api-version=2024-09-01", headers=headers, json={"text": text[:10000]})
                if mod.status_code == 200:
                    for cat in mod.json().get("categoriesAnalysis", []):
                        if cat.get("severity", 0) >= 4:
                            result["blocked"] = True
                            result["reasons"].append(f"harm:{cat.get('category')}")
            result["source"] = "Azure AI Content Safety"
        except httpx.HTTPError:
            result["source"] = "local rules (Content Safety unreachable)"
    return result
