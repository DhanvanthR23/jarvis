"""STT interface abstraction (plan2.md section 8).

The controller depends on this interface, never a specific STT engine directly.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import time
from typing import Optional


@dataclass(frozen=True)
class Transcript:
    """Immutable result of a speech-to-text operation."""
    text: str
    confidence: float          # 0.0–1.0
    language: str = 'en'
    timestamp: float = field(default_factory=time.time)
    audio_hash: str = ''       # SHA-256 of the raw audio bytes, for audit

    @staticmethod
    def compute_audio_hash(audio_bytes: bytes) -> str:
        """Compute SHA-256 hash of raw audio for audit metadata."""
        return hashlib.sha256(audio_bytes).hexdigest()


class SpeechToText(ABC):
    """Abstract STT interface.

    Implementations must:
    - Return a Transcript with a meaningful confidence score.
    - Compute and attach the audio_hash before returning.
    - Never retain raw audio after transcription completes.
    """

    @abstractmethod
    def transcribe(self, audio: bytes) -> Transcript:
        """Transcribe audio bytes into text.

        Args:
            audio: Raw audio data (PCM/WAV).

        Returns:
            Transcript with text, confidence, and audio_hash.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this STT backend is operational."""
        ...
