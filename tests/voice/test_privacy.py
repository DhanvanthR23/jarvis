"""Tests for Audio Privacy (G24.13)."""
import gc
import unittest
import weakref

from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
from jarvis.voice.runtime import VoiceRuntime
from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech


class DummySTT(SpeechToText):
    def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text="test", confidence=1.0, audio_hash="fake_hash")
    def is_available(self) -> bool: return True

class DummyTTS(TextToSpeech):
    def speak(self, text: str) -> None: pass
    def stop(self) -> None: pass
    def is_available(self) -> bool: return True

class TestAudioPrivacy(unittest.TestCase):
    def test_audio_bytes_are_dropped(self):
        cap = MockAudioCapture()
        rt = VoiceRuntime(cap, MockAudioPlayback(), DummySTT(), DummyTTS())
        
        rt.start_listening()
        
        # intercept the chunk to get a weakref
        original_stop = cap.stop
        chunk_ref = None
        data_ref = None
        
        def mock_stop():
            nonlocal chunk_ref, data_ref
            chunk = original_stop()
            chunk_ref = weakref.ref(chunk)
            # We can't weakref bytes directly, but we can verify the chunk object is gone.
            return chunk
            
        cap.stop = mock_stop
        
        rt.stop_listening()
        
        # Force garbage collection
        gc.collect()
        
        # The chunk should be dead
        self.assertIsNone(chunk_ref())

if __name__ == '__main__':
    unittest.main()
