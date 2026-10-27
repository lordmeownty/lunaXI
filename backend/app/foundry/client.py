"""Async client for Microsoft Foundry models (OpenAI v1-compatible surface)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import settings

log = logging.getLogger("luna.foundry")


class FoundryUnavailable(RuntimeError):
    """Raised when Foundry isn't configured or a call fails. Callers fall back."""


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

    def json(self) -> Any:
        txt = self.text.strip()
        return json.loads(txt[txt.find("{"):txt.rfind("}") + 1])


def _headers(api_key: str | None = None) -> dict:
    key = api_key or settings.foundry_api_key
    return {"api-key": key, "Authorization": f"Bearer {key}"}


async def chat(deployment: str, messages: list[dict], *, temperature: float | None = 0.4, max_tokens: int = 700,
               json_schema: dict | None = None, reasoning_effort: str | None = None) -> LLMResult:
    if not settings.foundry_enabled:
        raise FoundryUnavailable("Foundry not configured")
    from ..platform.governance import budget
    if budget.exhausted():
        raise FoundryUnavailable("Daily AI budget reached: serving deterministic answers")
    body: dict[str, Any] = {"model": deployment, "messages": messages, "max_completion_tokens": max_tokens}
    if temperature is not None:
        body["temperature"] = temperature
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if json_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": json_schema.get("title", "result"), "schema": json_schema, "strict": False}}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
            r = await client.post(f"{settings.base_url}/chat/completions", headers=_headers(), json=body)
            if r.status_code == 400 and temperature is not None and "temperature" in r.text:
                body.pop("temperature", None)
                r = await client.post(f"{settings.base_url}/chat/completions", headers=_headers(), json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        log.warning("Foundry chat failed (%s): %s", deployment, e)
        raise FoundryUnavailable(str(e)) from e
    usage = data.get("usage", {}) or {}
    msg = ((data.get("choices") or [{}])[0].get("message") or {})
    return LLMResult(msg.get("content") or "", data.get("model", deployment), usage.get("prompt_tokens", 0),
                     usage.get("completion_tokens", 0), int((time.perf_counter() - t0) * 1000))


async def transcribe(audio: bytes, filename: str, *, prompt: str = "") -> dict:
    if not settings.foundry_enabled:
        raise FoundryUnavailable("Foundry not configured")
    data = {"model": settings.transcribe_deployment, "response_format": "json"}
    if prompt:
        data["prompt"] = prompt
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{settings.base_url}/audio/transcriptions", headers=_headers(), data=data, files={"file": (filename, audio)})
            r.raise_for_status()
            out = r.json()
    except httpx.HTTPError as e:
        raise FoundryUnavailable(str(e)) from e
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


async def generate_image(prompt: str, size: str = "1024x1024") -> dict:
    if not (settings.foundry_enabled and settings.image_deployment):
        raise FoundryUnavailable("Image deployment not configured")
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{settings.base_url}/images/generations", headers=_headers(),
                                  json={"model": settings.image_deployment, "prompt": prompt, "size": size, "n": 1})
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise FoundryUnavailable(str(e)) from e
    item = (data.get("data") or [{}])[0]
    return {"b64": item.get("b64_json"), "url": item.get("url")}
