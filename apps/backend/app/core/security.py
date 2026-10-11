import asyncio
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from pydantic import BaseModel

from app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class Principal(BaseModel):
    user_id: str
    role: Literal["user", "curator", "admin"] = "user"


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    if not settings.auth_jwks_url or not settings.auth_issuer or not settings.auth_audience:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    if not settings.allowed_auth_algorithms or "none" in settings.allowed_auth_algorithms:
        raise HTTPException(status_code=503, detail="Authentication algorithms are misconfigured")

    try:
        signing_key = await asyncio.to_thread(
            _jwks_client(settings.auth_jwks_url).get_signing_key_from_jwt,
            credentials.credentials,
        )
    except PyJWKClientError as exc:
        raise HTTPException(
            status_code=503, detail="Authentication key service unavailable"
        ) from exc

    try:
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=settings.allowed_auth_algorithms,
            issuer=settings.auth_issuer,
            audience=settings.auth_audience,
            options={"require": ["exp", "iat", settings.auth_user_id_claim]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = claims.get(settings.auth_user_id_claim)
    role = claims.get(settings.auth_role_claim, "user")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid bearer token identity")
    if not isinstance(role, str) or role not in {"user", "curator", "admin"}:
        raise HTTPException(status_code=403, detail="Unsupported account role")

    return Principal(user_id=user_id, role=role)


def require_roles(*roles: Literal["user", "curator", "admin"]) -> Callable:
    async def role_dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return principal

    return role_dependency
