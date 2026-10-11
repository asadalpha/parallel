import httpx

from app.core.config import get_settings


class VoiceServiceUnavailable(RuntimeError):
    """Voice synthesis is not configured or failed."""


async def synthesize_story(text: str) -> tuple[bytes, str]:
    settings = get_settings()
    if (
        not settings.elevenlabs_api_key
        or not settings.elevenlabs_api_key.get_secret_value().strip()
        or not settings.elevenlabs_voice_id
    ):
        raise VoiceServiceUnavailable("ElevenLabs is not configured")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {"xi-api-key": settings.elevenlabs_api_key.get_secret_value()}
    payload = {"text": text, "model_id": settings.elevenlabs_model_id}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                params={"output_format": "mp3_44100_128"},
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise VoiceServiceUnavailable("ElevenLabs request failed") from exc

    return response.content, settings.elevenlabs_voice_id
