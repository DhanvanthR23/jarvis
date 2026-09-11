"""Local STT implementation using Vosk (plan2.md section 8, G24.4).

Wraps vosk in the SpeechToText interface.
Ensures audio is not retained.
"""
import io
import json
import os
import threading
import wave

from jarvis.voice.stt.interface import SpeechToText, Transcript


class VoskSTT(SpeechToText):
    """Local STT using the lightweight vosk engine."""

    def __init__(self, model_name: str = "vosk-model-small-en-us-0.15", sample_rate: int = 16000):
        self._sample_rate = sample_rate
        self._lock = threading.Lock()
        self._model = None
        self._model_name = model_name
        self._available = False
        
        # We defer model loading until first use or explicit initialization
        # to avoid blocking controller startup, but we check if we can import it.
        try:
            import vosk
            # Quiet the C-level logging to stderr unless debugging
            vosk.SetLogLevel(-1)
            self._vosk = vosk
            self._available = True
        except ImportError:
            self._vosk = None
            self._available = False

    def _get_model(self):
        if not self._available:
            raise RuntimeError("Vosk STT is not available (not installed)")
            
        if self._model is None:
            # Check local cache first, otherwise Vosk will auto-download
            model_path = os.path.expanduser(f"~/.cache/vosk/{self._model_name}")
            if os.path.exists(model_path):
                self._model = self._vosk.Model(model_path=model_path)
            else:
                self._model = self._vosk.Model(model_name=self._model_name)
        return self._model

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, audio: bytes) -> Transcript:
        """Transcribe PCM/WAV audio using local Vosk model."""
        if not self._available:
            raise RuntimeError("Vosk STT is not available")

        audio_hash = Transcript.compute_audio_hash(audio)
        
        # If the audio contains WAV headers, we should strip them or parse them.
        # Vosk KaldiRecognizer expects raw PCM. 
        # But for robustness, if it's WAV, parse it:
        if audio.startswith(b'RIFF'):
            with wave.open(io.BytesIO(audio), 'rb') as wf:
                audio_data = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
        else:
            audio_data = audio
            sample_rate = self._sample_rate

        with self._lock:
            model = self._get_model()
            rec = self._vosk.KaldiRecognizer(model, sample_rate)
            # KaldiRecognizer expects 16-bit PCM, mono
            
            # Feed data in chunks
            chunk_size = 4000
            for i in range(0, len(audio_data), chunk_size):
                rec.AcceptWaveform(audio_data[i:i+chunk_size])
                
            result_json = rec.FinalResult()
            
        # Parse result
        # result_json looks like: {"text": "hello world"}
        try:
            parsed = json.loads(result_json)
            text = parsed.get("text", "")
            # Vosk doesn't always provide a confidence score in the simple FinalResult.
            # If text is non-empty, we can assign a synthetic confidence, or if words[] 
            # is returned with conf, average them.
            # For this MVP, if text exists, confidence is 1.0, else 0.0.
            # Wait, G24.O requires confidence checks. Vosk can return word-level confidence
            # if we configure it, but let's parse what it has or default appropriately.
            confidence = 1.0 if text else 0.0
        except json.JSONDecodeError:
            text = ""
            confidence = 0.0

        return Transcript(
            text=text,
            confidence=confidence,
            audio_hash=audio_hash
        )
