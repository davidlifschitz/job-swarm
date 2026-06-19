from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient


@dataclass(frozen=True)
class SupabaseAuthConfig:
    url: str
    anon_key: str
    jwt_secret: str | None = None


def supabase_config_from_env(env: dict[str, str] | None = None) -> SupabaseAuthConfig | None:
    source = env if env is not None else os.environ
    url = (source.get("SUPABASE_URL") or "").strip().rstrip("/")
    anon_key = (source.get("SUPABASE_ANON_KEY") or "").strip()
    jwt_secret = (source.get("SUPABASE_JWT_SECRET") or "").strip() or None
    if not url or not anon_key:
        return None
    return SupabaseAuthConfig(url=url, anon_key=anon_key, jwt_secret=jwt_secret)


def supabase_auth_enabled(env: dict[str, str] | None = None) -> bool:
    return supabase_config_from_env(env) is not None


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def decode_access_token(token: str, config: SupabaseAuthConfig) -> dict[str, Any]:
    if config.jwt_secret:
        return jwt.decode(
            token,
            config.jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    signing_key = _jwks_client(config.url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[signing_key.algorithm_name],
        audience="authenticated",
    )


def user_id_from_claims(claims: dict[str, Any]) -> str:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidTokenError("token missing subject")
    return subject.strip()


def validate_access_token(token: str, config: SupabaseAuthConfig) -> dict[str, Any]:
    claims = decode_access_token(token, config)
    user_id_from_claims(claims)
    return claims