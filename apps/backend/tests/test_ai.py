from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.services import ai
from app.services.ai import AIProviderError


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": '{"suggestion":"A grounded suggestion."}'}}]}


class FakeClient:
    def __init__(self) -> None:
        self.request: dict[str, object] = {}

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(
        self, url: str, *, headers: dict[str, str], json: dict[str, object]
    ) -> FakeResponse:
        self.request = {"url": url, "headers": headers, "json": json}
        return FakeResponse()


@pytest.mark.asyncio
async def test_openrouter_uses_configured_gemma_4_model_and_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeClient()
    settings = SimpleNamespace(
        ai_provider="openrouter",
        ai_base_url="https://openrouter.ai/api/v1",
        ai_model="google/gemma-4-26b-a4b-it:free",
        ai_api_key=None,
        openrouter_api_key=SecretStr("test-only-key"),
        ai_timeout_seconds=2.0,
    )
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **_: fake_client)

    result = await ai.complete_json("system", "user")

    assert result == {"suggestion": "A grounded suggestion."}
    assert fake_client.request["url"] == "https://openrouter.ai/api/v1/chat/completions"
    request = fake_client.request["json"]
    assert request["model"] == "google/gemma-4-26b-a4b-it:free"
    assert request["response_format"] == {"type": "json_object"}
    assert fake_client.request["headers"]["Authorization"] == "Bearer test-only-key"


@pytest.mark.asyncio
async def test_openrouter_without_key_is_unconfigured_not_a_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        ai_provider="openrouter",
        ai_base_url="https://openrouter.ai/api/v1",
        ai_model="google/gemma-4-26b-a4b-it:free",
        ai_api_key=SecretStr(""),
        openrouter_api_key=SecretStr(""),
        ai_timeout_seconds=2.0,
    )
    monkeypatch.setattr(ai, "get_settings", lambda: settings)

    with pytest.raises(AIProviderError, match="API key is not configured"):
        await ai.complete_json("system", "user")
