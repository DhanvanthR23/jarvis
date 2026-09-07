"""Audio capture/playback abstraction (plan2.md section 15).

Handles microphone capture and speaker playback.
Normal operation: mic → temporary audio → STT → discard.
No permanent voice archive.
"""
import hashlib
import io
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioChunk:
    """A chunk of captured audio data."""
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2   # bytes per sample (16-bit)
    timestamp: float = field(default_factory=time.time)

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate == 0 or self.channels == 0 or self.sample_width == 0:
            return 0.0
        return len(self.data) / (self.sample_rate * self.channels * self.sample_width)

    def audio_hash(self) -> str:
        """SHA-256 of raw audio bytes for audit metadata (not retained)."""
        return hashlib.sha256(self.data).hexdigest()

    def to_wav(self) -> bytes:
        """Convert raw PCM to WAV format in memory."""
        buf = io.BytesIO()
        data_size = len(self.data)
        # WAV header
        buf.write(b'RIFF')
        buf.write(struct.pack('<I', 36 + data_size))
        buf.write(b'WAVE')
        buf.write(b'fmt ')
        buf.write(struct.pack('<I', 16))                          # chunk size
        buf.write(struct.pack('<H', 1))                           # PCM
        buf.write(struct.pack('<H', self.channels))
        buf.write(struct.pack('<I', self.sample_rate))
        byte_rate = self.sample_rate * self.channels * self.sample_width
        buf.write(struct.pack('<I', byte_rate))
        block_align = self.channels * self.sample_width
        buf.write(struct.pack('<H', block_align))
        buf.write(struct.pack('<H', self.sample_width * 8))       # bits/sample
        buf.write(b'data')
        buf.write(struct.pack('<I', data_size))
        buf.write(self.data)
        return buf.getvalue()


class AudioCapture(ABC):
    """Abstract microphone capture interface."""

    @abstractmethod
    def start(self) -> None:
        """Begin capturing audio from the microphone."""
        ...

    @abstractmethod
    def stop(self) -> AudioChunk:
        """Stop capturing and return the captured audio.

        The raw audio must be discarded after STT processes it.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether microphone hardware is accessible."""
        ...


class AudioPlayback(ABC):
    """Abstract speaker playback interface."""

    @abstractmethod
    def play(self, audio: bytes) -> None:
        """Play audio bytes through the speaker."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop any in-progress playback."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether speaker hardware is accessible."""
        ...


class MockAudioCapture(AudioCapture):
    """Test-only audio capture that returns synthetic audio."""

    def __init__(self):
        self._recording = False
        self._data = b''

    def start(self) -> None:
        self._recording = True
        self._data = b'\x00' * 32000  # 1 second of silence at 16kHz/16bit/mono

    def stop(self) -> AudioChunk:
        self._recording = False
        chunk = AudioChunk(data=self._data)
        self._data = b''
        return chunk

    def is_available(self) -> bool:
        return True


class MockAudioPlayback(AudioPlayback):
    """Test-only audio playback that records what was played."""

    def __init__(self):
        self.played: list = []
        self.stopped = False

    def play(self, audio: bytes) -> None:
        self.played.append(audio)

    def stop(self) -> None:
        self.stopped = True

    def is_available(self) -> bool:
        return True
