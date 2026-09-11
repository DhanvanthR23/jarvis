"""Local STT implementation using faster-whisper (plan5.md section G27.2).

Wraps faster-whisper in the SpeechToText interface.
Ensures audio is not retained.
"""
import io
import math
import threading
import wave

from jarvis.voice.stt.interface import SpeechToText, Transcript


class FasterWhisperSTT(SpeechToText):
    """Local STT using faster-whisper."""

    def __init__(self, model_size: str = "base.en", compute_type: str = "int8", sample_rate: int = 16000):
        self._sample_rate = sample_rate
        self._model_size = model_size
        self._compute_type = compute_type
        self._lock = threading.Lock()
        self._model = None
        self._available = False
        
        try:
            from faster_whisper import WhisperModel
            self._WhisperModel = WhisperModel
            self._available = True
        except ImportError:
            self._WhisperModel = None
            self._available = False

    def _get_model(self):
        if not self._available:
            raise RuntimeError("faster-whisper is not available (not installed)")
            
        if self._model is None:
            # Load the model on CPU with int8 quantization to prevent thermal throttling
            print(f"\n⏳ Loading faster-whisper model '{self._model_size}' (this may take a minute if downloading for the first time)...", flush=True)
            self._model = self._WhisperModel(self._model_size, device="cpu", compute_type=self._compute_type)
            print("✅ Model loaded!", flush=True)
        return self._model

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, audio: bytes) -> Transcript:
        if not self._available:
            raise RuntimeError("faster-whisper is not available")

        audio_hash = Transcript.compute_audio_hash(audio)
        
        if audio.startswith(b'RIFF'):
            import numpy as np
            with wave.open(io.BytesIO(audio), 'rb') as wf:
                audio_data = wf.readframes(wf.getnframes())
                wf.getframerate()
            # Convert 16-bit PCM to float32 for faster-whisper
            audio_np = np.frombuffer(audio_data, np.int16).astype(np.float32) / 32768.0
        else:
            import numpy as np
            audio_np = np.frombuffer(audio, np.int16).astype(np.float32) / 32768.0

        with self._lock:
            model = self._get_model()
            # Transcribe
            segments, _info = model.transcribe(audio_np, beam_size=1)
            
            text = ""
            total_prob = 0.0
            count = 0
            
            for segment in segments:
                text += segment.text + " "
                # Convert avg_logprob to probability: math.exp(avg_logprob)
                # Penalty for no_speech_prob
                seg_prob = math.exp(segment.avg_logprob) * (1.0 - segment.no_speech_prob)
                total_prob += seg_prob
                count += 1
                
            text = text.strip()
            confidence = (total_prob / count) if count > 0 else 0.0

        return Transcript(
            text=text,
            confidence=confidence,
            audio_hash=audio_hash
        )
