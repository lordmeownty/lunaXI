"""Authentication + role-based authorisation.

AUTH_MODE=demo  : "Sign in with Microsoft" button performs a simulated sign-in (no real token). The browser
                  sends X-Demo-Role. Default persona is Luna.Director (sees everything).
AUTH_MODE=entra : real Microsoft Entra ID access tokens are validated (signature, issuer, audience, tenant, expiry).

Luna.Director can preview any other role with the X-View-As header ("View as"). Every switch is audited, and
separation of duties still applies (nobody approves a package they submitted).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, Request

from ..config import settings

log = logging.getLogger("luna.auth")

ROLES = ["Luna.Fan", "Luna.Analyst", "Luna.Broadcaster", "Luna.Editor", "Luna.Admin", "Luna.Director"]
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}
PREVIEWABLE = ROLES[:-1]

CAPABILITIES: dict[str, set[str]] = {
    "match.view": set(ROLES), "luna.ask": set(ROLES), "luna.voice": set(ROLES), "recap.create": set(ROLES),
    "analysis.deep": {"Luna.Analyst", "Luna.Broadcaster", "Luna.Editor", "Luna.Admin", "Luna.Director"},
    "studio.use": {"Luna.Broadcaster", "Luna.Editor", "Luna.Admin", "Luna.Director"},
    "package.submit": {"Luna.Broadcaster", "Luna.Editor", "Luna.Admin", "Luna.Director"},
    "package.approve": {"Luna.Editor", "Luna.Admin", "Luna.Director"},
    "ops.view": {"Luna.Admin", "Luna.Director"},
    "ops.broadcast_events": {"Luna.Admin", "Luna.Director"},
    "role.preview": {"Luna.Director"},
    "a2a.invoke": set(ROLES),
}

DEMO_USERS = {
    "Luna.Director": ("Alex Morgan-Reyes", "alex.director@contoso-sports.example"),
    "Luna.Fan": ("Maya Fernandes", "maya.fernandes@contoso-sports.example"),
    "Luna.Analyst": ("Dev Kapoor", "dev.kapoor@contoso-sports.example"),
    "Luna.Broadcaster": ("Sophie Turner-Hall", "sophie.th@contoso-sports.example"),
    "Luna.Editor": ("Aaron Okeke", "aaron.okeke@contoso-sports.example"),
    "Luna.Admin": ("Priya Raman", "priya.raman@contoso-sports.example"),
}


@dataclass
class User:
    oid: str
    name: str
    email: str
    roles: list[str]
    tenant: str
    auth: str
    real_roles: list[str] = field(default_factory=list)
    viewing_as: str | None = None

    @property
    def primary_role(self) -> str:
        return max(self.roles, key=lambda r: ROLE_RANK.get(r, -1)) if self.roles else "Luna.Fan"

    def can(self, capability: str) -> bool:
        return bool(set(self.roles) & CAPABILITIES.get(capability, set()))

    def public(self) -> dict:
        return {"oid": self.oid, "name": self.name, "email": self.email, "roles": self.roles,
                "primary_role": self.primary_role, "tenant": self.tenant, "auth": self.auth,
                "real_roles": self.real_roles or self.roles, "viewing_as": self.viewing_as,
                "can_preview": "Luna.Director" in (self.real_roles or self.roles), "previewable_roles": PREVIEWABLE,
                "capabilities": sorted(c for c in CAPABILITIES if self.can(c))}


class _JWKS:
    _client, _created = None, 0.0

    @classmethod
    def client(cls):
        import jwt
        if cls._client is None or time.time() - cls._created > 3600:
            cls._client = jwt.PyJWKClient(f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys", cache_keys=True)
            cls._created = time.time()
        return cls._client


def validate_entra_token(token: str) -> dict:
    import jwt
    if not (settings.entra_tenant_id and settings.entra_api_client_id):
        raise HTTPException(500, "Entra is enabled but ENTRA_TENANT_ID / ENTRA_API_CLIENT_ID are not set")
    audiences = [a for a in {settings.entra_audience, settings.entra_api_client_id, f"api://{settings.entra_api_client_id}"} if a]
    try:
        key = _JWKS.client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=audiences,
                            issuer=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0",
                            options={"require": ["exp", "iat", "aud", "iss"]}, leeway=60)
    except Exception as e:  # noqa: BLE001
        log.info("token rejected: %s", e)
        raise HTTPException(401, "Invalid or expired Microsoft Entra token", headers={"WWW-Authenticate": "Bearer"})
    if claims.get("tid") != settings.entra_tenant_id:
        raise HTTPException(401, "Token issued for a different tenant")
    return claims


async def current_user(request: Request, authorization: str | None = Header(None), x_demo_role: str | None = Header(None),
                       x_view_as: str | None = Header(None)) -> User:
    if settings.entra_enabled:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Sign in with Microsoft", headers={"WWW-Authenticate": "Bearer"})
        c = validate_entra_token(authorization.split(" ", 1)[1])
        roles = [r for r in c.get("roles", []) if r in ROLE_RANK] or ["Luna.Fan"]
        user = User(c.get("oid", ""), c.get("name", "Signed-in user"), c.get("preferred_username", ""), roles, c.get("tid", ""), "entra")
    else:
        role = x_demo_role if x_demo_role in ROLE_RANK else "Luna.Director"
        name, email = DEMO_USERS[role]
        user = User(f"demo-{role.split('.')[1].lower()}", name, email, [role], "contoso-sports (demo)", "demo")
    user.real_roles = list(user.roles)
    if x_view_as and x_view_as in PREVIEWABLE and "Luna.Director" in user.real_roles:
        user.roles, user.viewing_as = [x_view_as], x_view_as
    request.state.user = user
    return user


def require(capability: str):
    async def _dep(user: User = Depends(current_user)) -> User:
        if not user.can(capability):
            raise HTTPException(403, f"Your role ({user.primary_role}) cannot perform '{capability}'")
        return user
    return _dep
