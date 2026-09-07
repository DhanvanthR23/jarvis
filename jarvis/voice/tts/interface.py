"""TTS interface abstraction (plan2.md section 12).

TTS has no authority. It can only speak text that has already passed through
the Controller's OutputSecurityFilter.
"""
from abc import ABC, abstractmethod


class TextToSpeech(ABC):
    """Abstract TTS interface.

    Implementations must:
    - Accept only pre-filtered text (the caller is responsible for filtering).
    - Never call tools, policy, MCP, or memory directly.
    - Never retain spoken text beyond the duration of playback.
    """

    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak the given text through the audio output device.

        Args:
            text: Pre-filtered text safe for audible presentation.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Immediately cancel any in-progress speech."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this TTS backend is operational."""
        ...
