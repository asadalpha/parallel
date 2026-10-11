from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security


@pytest.fixture
def token_keys() -> tuple[Ed25519PrivateKey, object]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def _token(private_key: Ed25519PrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://parallel.example",
        "aud": "https://parallel.example",
        "id": "better-auth-user-123",
        "role": "curator",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="EdDSA")


@pytest.mark.asyncio
async def test_better_auth_jwks_token_resolves_signed_user_and_role(
    monkeypatch: pytest.MonkeyPatch,
    token_keys: tuple[Ed25519PrivateKey, object],
) -> None:
    private_key, public_key = token_keys

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> SimpleNamespace:
            return SimpleNamespace(key=public_key)

    settings = SimpleNamespace(
        auth_jwks_url="https://parallel.example/api/auth/jwks",
        auth_issuer="https://parallel.example",
        auth_audience="https://parallel.example",
        auth_user_id_claim="id",
        auth_role_claim="role",
        allowed_auth_algorithms=["EdDSA"],
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_jwks_client", lambda _: FakeJwksClient())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token(private_key))

    principal = await security.get_current_principal(credentials)

    assert principal.user_id == "better-auth-user-123"
    assert principal.role == "curator"


@pytest.mark.asyncio
async def test_auth_rejects_wrong_audience(
    monkeypatch: pytest.MonkeyPatch,
    token_keys: tuple[Ed25519PrivateKey, object],
) -> None:
    private_key, public_key = token_keys

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _: str) -> SimpleNamespace:
            return SimpleNamespace(key=public_key)

    settings = SimpleNamespace(
        auth_jwks_url="https://parallel.example/api/auth/jwks",
        auth_issuer="https://parallel.example",
        auth_audience="https://parallel.example",
        auth_user_id_claim="id",
        auth_role_claim="role",
        allowed_auth_algorithms=["EdDSA"],
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_jwks_client", lambda _: FakeJwksClient())
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=_token(private_key, aud="https://other.example")
    )

    with pytest.raises(HTTPException) as error:
        await security.get_current_principal(credentials)

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_is_unavailable_until_jwks_issuer_and_audience_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        auth_jwks_url=None,
        auth_issuer=None,
        auth_audience=None,
        allowed_auth_algorithms=["EdDSA"],
    )
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as error:
        await security.get_current_principal(credentials)

    assert error.value.status_code == 503
