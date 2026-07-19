"""
Input Handling Agent — Google ADK Agent + A2A Server.

Handles file ingestion and audio transcription. For audio files, uses
Gemini native audio understanding via the ADK instead of OpenAI Whisper.
The text-transcript path remains unchanged.

Fallback chain for audio:
    1. Gemini (via ADK) — preferred, if GEMINI_API_KEY is set
    2. OpenAI Whisper — fallback, if OPENAI_API_KEY is set
    3. Error — if neither key is available
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Optional

from threadline.models import MeetingTranscript

logger = logging.getLogger(__name__)

# Audio file extensions that trigger transcription
_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".flac", ".webm"}

AGENT_NAME = "input_agent"
AGENT_DESCRIPTION = (
    "Handles meeting file ingestion. Reads text transcripts directly and "
    "transcribes audio files using Gemini native audio understanding. "
    "Returns a MeetingTranscript object ready for extraction."
)


class InputAgentRunner:
    """
    Encapsulates the Input Agent's logic for both text and audio ingestion.
    """

    def __init__(
        self,
        gemini_api_key: str = "",
        gemini_model: str = "gemini-2.0-flash",
        openai_api_key: str = "",
    ) -> None:
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.openai_api_key = openai_api_key

    def ingest(
        self,
        source: str | Path,
        meeting_id: str | None = None,
        content: bytes | None = None,
    ) -> tuple[MeetingTranscript, bool]:
        """
        Read the source file and return (MeetingTranscript, is_audio).

        Args:
            source: Path to the file (or filename for content-based input).
            meeting_id: Optional meeting ID override.
            content: Optional pre-read file content (e.g., from upload).

        Returns:
            Tuple of (MeetingTranscript, is_audio_flag).
        """
        source = Path(source) if isinstance(source, str) else source
        if meeting_id is None:
            meeting_id = source.stem

        is_audio = source.suffix.lower() in _AUDIO_EXTENSIONS

        if is_audio:
            return MeetingTranscript(
                id=meeting_id,
                source_file=str(source),
                text="[AUDIO — pending transcription]",
                meeting_title=source.stem.replace("_", " ").title(),
            ), True

        if content is not None:
            text = content.decode("utf-8", errors="replace")
        else:
            text = source.read_text(encoding="utf-8", errors="replace")

        return MeetingTranscript(
            id=meeting_id,
            source_file=str(source),
            text=text,
            meeting_title=source.stem.replace("_", " ").title(),
        ), False

    def transcribe(
        self,
        transcript: MeetingTranscript,
        source: Path,
        content: bytes | None = None,
    ) -> MeetingTranscript:
        """
        Transcribe an audio file. Tries Gemini first, falls back to Whisper.

        Args:
            transcript: The MeetingTranscript with placeholder text.
            source: Path to the audio file.
            content: Optional pre-read audio bytes.

        Returns:
            Updated MeetingTranscript with transcribed text.

        Raises:
            RuntimeError: If no API key is available for either provider.
        """
        # Try Gemini native audio understanding first
        if self.gemini_api_key:
            return self._transcribe_gemini(transcript, source, content)

        # Fall back to OpenAI Whisper
        if self.openai_api_key:
            return self._transcribe_whisper(transcript, source, content)

        raise RuntimeError(
            "Audio transcription requires either GEMINI_API_KEY or OPENAI_API_KEY. "
            "Upload a .txt transcript file instead, or set one of these in .env."
        )

    def _transcribe_gemini(
        self,
        transcript: MeetingTranscript,
        source: Path,
        content: bytes | None = None,
    ) -> MeetingTranscript:
        """
        Transcribe audio using Gemini native audio understanding.

        Gemini processes raw audio as a multimodal input and generates
        a verbatim transcription when prompted correctly.
        """
        import google.generativeai as genai

        genai.configure(api_key=self.gemini_api_key)
        model = genai.GenerativeModel(self.gemini_model)

        # Read audio content
        if content is None:
            content = source.read_bytes()

        # Determine MIME type from extension
        mime_map = {
            ".mp3": "audio/mpeg",
            ".mp4": "audio/mp4",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".webm": "audio/webm",
        }
        mime_type = mime_map.get(source.suffix.lower(), "audio/mpeg")

        # Send audio to Gemini with transcription prompt
        response = model.generate_content([
            {
                "mime_type": mime_type,
                "data": content,
            },
            (
                "Please provide a complete, verbatim transcription of this audio recording. "
                "Include speaker labels if distinguishable (e.g., 'Speaker 1:', 'Speaker 2:'). "
                "Transcribe every word exactly as spoken, including filler words. "
                "Do not summarize, paraphrase, or add commentary. "
                "Return ONLY the transcription text."
            ),
        ])

        transcribed_text = response.text or ""
        # Strip any accidental markdown code fencing
        transcribed_text = re.sub(r"^```(?:\w+)?\s*", "", transcribed_text.strip())
        transcribed_text = re.sub(r"\s*```$", "", transcribed_text)

        logger.info(
            "Gemini transcribed %s: %d characters",
            source.name, len(transcribed_text),
        )
        return transcript.model_copy(update={"text": transcribed_text})

    def _transcribe_whisper(
        self,
        transcript: MeetingTranscript,
        source: Path,
        content: bytes | None = None,
    ) -> MeetingTranscript:
        """
        Transcribe audio using OpenAI Whisper API (legacy fallback).
        """
        from openai import OpenAI

        client = OpenAI(api_key=self.openai_api_key)

        if content is not None:
            audio_file = io.BytesIO(content)
            audio_file.name = source.name
            response = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, response_format="text"
            )
        else:
            with open(source, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="text"
                )

        logger.info("Whisper transcribed %s (fallback)", source.name)
        return transcript.model_copy(update={"text": str(response)})


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation
# ─────────────────────────────────────────────────────────────────────────────

def create_input_adk_agent():
    """Create a Google ADK Agent for input handling."""
    try:
        from google.adk.agents import Agent

        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Input Handling Agent for the Threadline meeting intelligence system. "
                "You receive meeting files (text transcripts or audio recordings) and prepare them "
                "for downstream processing. For text files, read them directly. For audio files, "
                "transcribe them using Gemini native audio understanding."
            ),
            tools=[],
        )
        logger.info("Created ADK Input Agent: %s", AGENT_NAME)
        return agent
    except ImportError:
        logger.warning("google-adk not installed — Input ADK agent unavailable")
        return None
