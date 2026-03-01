"""Transcription service with Groq Whisper (primary) and Deepgram (fallback)."""

import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqTranscriber:
    """Transcribe audio using Groq Whisper API (free, fast)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def transcribe(self, audio_bytes: bytes) -> str:
        logger.info("Groq transcription, audio size: %d bytes", len(audio_bytes))

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = Path(f.name)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    GROQ_WHISPER_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (tmp_path.name, audio_bytes, "audio/ogg")},
                    data={
                        "model": "whisper-large-v3",
                        "language": "ru",
                        "response_format": "json",
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                transcript = result.get("text", "")
                logger.info("Groq transcription complete: %d chars", len(transcript))
                return transcript
        finally:
            tmp_path.unlink(missing_ok=True)


class DeepgramTranscriber:
    """Fallback: transcribe audio using Deepgram Nova-3."""

    def __init__(self, api_key: str) -> None:
        from deepgram import AsyncDeepgramClient

        self.client = AsyncDeepgramClient(api_key=api_key)

    async def transcribe(self, audio_bytes: bytes) -> str:
        logger.info("Deepgram transcription, audio size: %d bytes", len(audio_bytes))

        response = await self.client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-3",
            language="ru",
            punctuate=True,
            smart_format=True,
        )

        transcript = (
            response.results.channels[0].alternatives[0].transcript
            if response.results
            and response.results.channels
            and response.results.channels[0].alternatives
            else ""
        )

        logger.info("Deepgram transcription complete: %d chars", len(transcript))
        return transcript


def get_transcriber(groq_api_key: str = "", deepgram_api_key: str = ""):
    """Get best available transcriber. Groq preferred (free)."""
    if groq_api_key:
        return GroqTranscriber(groq_api_key)
    if deepgram_api_key:
        return DeepgramTranscriber(deepgram_api_key)
    return None
