"""Central configuration. Secrets come from Azure Key Vault (production) or .env (local)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv()
except Exception:  # pragma: no cover
    pass

log = logging.getLogger("luna.config")

# Secrets that may be pulled from Key Vault: env var name -> Key Vault secret name
KEY_VAULT_SECRETS = {"FOUNDRY_API_KEY": "foundry-api-key", "CONTENT_SAFETY_KEY": "content-safety-key",
                     "STREAM_TICKET_SECRET": "stream-ticket-secret"}
SECRET_SOURCE: dict[str, str] = {}


def load_key_vault_secrets() -> None:
    """If KEY_VAULT_URI is set, fetch secrets with the app's managed identity (DefaultAzureCredential)."""
    uri = os.getenv("KEY_VAULT_URI", "").strip()
    for env_name in KEY_VAULT_SECRETS:
        SECRET_SOURCE[env_name] = ".env" if os.getenv(env_name) else "not set"
    if not uri:
        return
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        client = SecretClient(vault_url=uri, credential=DefaultAzureCredential())
        for env_name, secret_name in KEY_VAULT_SECRETS.items():
            try:
                os.environ[env_name] = client.get_secret(secret_name).value
                SECRET_SOURCE[env_name] = "Azure Key Vault"
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        log.warning("Key Vault not reachable (%s); using environment variables", e)


load_key_vault_secrets()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    foundry_endpoint: str = field(default_factory=lambda: _env("FOUNDRY_ENDPOINT").rstrip("/"))
    foundry_api_key: str = field(default_factory=lambda: _env("FOUNDRY_API_KEY"))
    foundry_api_path: str = field(default_factory=lambda: _env("FOUNDRY_API_PATH", "/openai/v1"))
    fast_deployment: str = field(default_factory=lambda: _env("FOUNDRY_FAST_DEPLOYMENT", "gpt-6-luna"))
    reasoning_deployment: str = field(default_factory=lambda: _env("FOUNDRY_REASONING_DEPLOYMENT", "gpt-6-sol"))
    transcribe_deployment: str = field(default_factory=lambda: _env("FOUNDRY_TRANSCRIBE_DEPLOYMENT", "gpt-transcribe"))
    realtime_deployment: str = field(default_factory=lambda: _env("FOUNDRY_REALTIME_DEPLOYMENT", "gpt-realtime-2.1"))
    realtime_voice: str = field(default_factory=lambda: _env("FOUNDRY_REALTIME_VOICE", "marin"))
    image_deployment: str = field(default_factory=lambda: _env("FOUNDRY_IMAGE_DEPLOYMENT", ""))
    realtime_client_secret_url: str = field(default_factory=lambda: _env("FOUNDRY_REALTIME_CLIENT_SECRET_URL"))
    realtime_webrtc_url: str = field(default_factory=lambda: _env("FOUNDRY_REALTIME_WEBRTC_URL"))
    decision_mode: str = field(default_factory=lambda: _env("FOUNDRY_DECISION_MODE", "chat"))
    decision_deployment: str = field(default_factory=lambda: _env("FOUNDRY_DECISION_DEPLOYMENT", "microsoft-decision-1"))
    decision_endpoint: str = field(default_factory=lambda: _env("FOUNDRY_DECISION_ENDPOINT"))
    decision_api_key: str = field(default_factory=lambda: _env("FOUNDRY_DECISION_API_KEY"))
    content_safety_endpoint: str = field(default_factory=lambda: _env("CONTENT_SAFETY_ENDPOINT").rstrip("/"))
    content_safety_key: str = field(default_factory=lambda: _env("CONTENT_SAFETY_KEY"))
    key_vault_uri: str = field(default_factory=lambda: _env("KEY_VAULT_URI"))
    # AUTH_MODE: demo (Microsoft-style sign-in, simulated) | entra (real Entra token validation)
    auth_mode: str = field(default_factory=lambda: _env("AUTH_MODE", "demo").lower())
    entra_tenant_id: str = field(default_factory=lambda: _env("ENTRA_TENANT_ID"))
    entra_api_client_id: str = field(default_factory=lambda: _env("ENTRA_API_CLIENT_ID"))
    entra_audience: str = field(default_factory=lambda: _env("ENTRA_AUDIENCE"))
    # ORCHESTRATOR: builtin | agent_framework (Microsoft Agent Framework, if installed)
    orchestrator: str = field(default_factory=lambda: _env("ORCHESTRATOR", "agent_framework").lower())
    eventhub_connection: str = field(default_factory=lambda: _env("EVENTHUB_CONNECTION_STRING"))
    eventhub_name: str = field(default_factory=lambda: _env("EVENTHUB_NAME", "match-events"))
    servicebus_connection: str = field(default_factory=lambda: _env("SERVICEBUS_CONNECTION_STRING"))
    servicebus_topic: str = field(default_factory=lambda: _env("SERVICEBUS_TOPIC", "luna-packages"))
    fully_qualified_namespace_eh: str = field(default_factory=lambda: _env("EVENTHUB_FQDN"))
    fully_qualified_namespace_sb: str = field(default_factory=lambda: _env("SERVICEBUS_FQDN"))
    gate_high: float = field(default_factory=lambda: _float("GATE_HIGH_CONFIDENCE", 0.85))
    gate_low: float = field(default_factory=lambda: _float("GATE_LOW_CONFIDENCE", 0.60))
    price_fast_in: float = field(default_factory=lambda: _float("PRICE_FAST_IN", 0.20))
    price_fast_out: float = field(default_factory=lambda: _float("PRICE_FAST_OUT", 1.25))
    price_reason_in: float = field(default_factory=lambda: _float("PRICE_REASON_IN", 1.75))
    price_reason_out: float = field(default_factory=lambda: _float("PRICE_REASON_OUT", 14.0))
    daily_budget_usd: float = field(default_factory=lambda: _float("DAILY_AI_BUDGET_USD", 25.0))
    data_dir: Path = field(default_factory=lambda: Path(_env("LUNA_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data"))))
    state_dir: Path = field(default_factory=lambda: Path(_env("LUNA_STATE_DIR", str(Path(__file__).resolve().parents[2] / ".state"))))
    cors_origins: list[str] = field(default_factory=lambda: [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()])
    appinsights_connection_string: str = field(default_factory=lambda: _env("APPLICATIONINSIGHTS_CONNECTION_STRING"))
    request_timeout_s: float = field(default_factory=lambda: _float("FOUNDRY_TIMEOUT_S", 45.0))
    rate_limit_per_min: float = field(default_factory=lambda: _float("RATE_LIMIT_PER_MIN", 60))

    @property
    def foundry_enabled(self) -> bool:
        return bool(self.foundry_endpoint and self.foundry_api_key)

    @property
    def base_url(self) -> str:
        return f"{self.foundry_endpoint}{self.foundry_api_path}"

    @property
    def entra_enabled(self) -> bool:
        return self.auth_mode == "entra"


settings = Settings()
