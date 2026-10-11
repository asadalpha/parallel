import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """The optional configured inference provider could not fulfill a request."""


async def complete_json(
    system_prompt: str, user_prompt: str, *, max_tokens: int = 512
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ai_base_url or not settings.ai_model:
        raise AIProviderError("AI inference is not configured")
    openrouter_key = next(
        (
            key
            for key in (settings.openrouter_api_key, settings.ai_api_key)
            if key and key.get_secret_value().strip()
        ),
        None,
    )
    if settings.ai_provider == "openrouter" and openrouter_key is None:
        raise AIProviderError("OpenRouter API key is not configured")
    if settings.ai_provider not in {"openrouter", "ollama", "openai_compatible"}:
        raise AIProviderError("Unsupported AI provider")

    endpoint = settings.ai_base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"

    headers = {"Content-Type": "application/json"}
    api_key = openrouter_key if settings.ai_provider == "openrouter" else settings.ai_api_key
    if api_key and api_key.get_secret_value().strip():
        headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"

    payload = {
        "model": settings.ai_model,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("AI response content was not text")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("AI response was not a JSON object")
        return result
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("AI provider request failed", exc_info=exc)
        raise AIProviderError("AI provider request failed") from exc
