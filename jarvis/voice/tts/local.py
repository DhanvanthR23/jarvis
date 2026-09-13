"""Local TTS implementation using Piper (plan2.md section 12, G24.5).

Wraps piper-tts in the TextToSpeech interface.
TTS has no authority and only speaks filtered text.
"""
import io
import wave

from jarvis.voice.audio import AudioPlayback
from jarvis.voice.tts.interface import TextToSpeech


class PiperTTS(TextToSpeech):
    """Local TTS using the Piper engine."""

    def __init__(self, playback: AudioPlayback, model_path: str | None = None):
        self._playback = playback
        self._available = False
        self._voice = None
        
        try:
            import piper
            self._piper = piper
            self._available = True
        except ImportError:
            self._piper = None
            self._available = False

        self._model_path = model_path or "en_GB-alan-medium.onnx"
        self._config_path = self._model_path + ".json"

    def is_available(self) -> bool:
        return self._available
        
    def _ensure_model(self):
        import os
        if not os.path.exists(self._model_path) or not os.path.exists(self._config_path):
            print(f"Downloading default Piper model: {self._model_path}...")
            import urllib.request
            # Auto-download a lightweight default english model if missing
            base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium"
            urllib.request.urlretrieve(f"{base_url}/en_GB-alan-medium.onnx", self._model_path)
            urllib.request.urlretrieve(f"{base_url}/en_GB-alan-medium.onnx.json", self._config_path)
            
        if self._voice is None:
            self._voice = self._piper.PiperVoice.load(self._model_path, config_path=self._config_path)

    def speak(self, text: str) -> None:
        """Synthesize and play the text synchronously."""
        if not self._available:
            raise RuntimeError("Piper TTS is not available")
        if not self._playback.is_available():
            raise RuntimeError("Audio playback is not available")

        self._ensure_model()
        
        import io
        import wave
        
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            # Piper synthesize_wav will write directly to the wave file
            self._voice.synthesize_wav(text, wf)
            
        wav_data = buf.getvalue()
        
        # Play it synchronously (blocks until playback finishes)
        self._playback.play(wav_data)

    def stop(self) -> None:
        """Stop playback immediately."""
        self._playback.stop()
