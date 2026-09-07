"""Tests for VoiceRuntime."""
import unittest
from jarvis.voice.runtime import VoiceRuntime
from jarvis.voice.state import VoiceState
from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech


class MockSTT(SpeechToText):
    def transcribe(self, audio: bytes) -> Transcript:
        if b'fail' in audio:
            raise RuntimeError("STT failed")
        return Transcript(text="hello", confidence=0.9)
    def is_available(self) -> bool: return True


class MockTTS(TextToSpeech):
    def speak(self, text: str) -> None: pass
    def stop(self) -> None: pass
    def is_available(self) -> bool: return True


class TestVoiceRuntime(unittest.TestCase):
    def setUp(self):
        self.cap = MockAudioCapture()
        self.pb = MockAudioPlayback()
        self.stt = MockSTT()
        self.tts = MockTTS()
        self.runtime = VoiceRuntime(self.cap, self.pb, self.stt, self.tts)

    def test_start_listening(self):
        self.runtime.start_listening()
        self.assertEqual(self.runtime.state, VoiceState.LISTENING)
        self.assertTrue(self.cap._recording)

    def test_stop_listening_success(self):
        self.runtime.start_listening()
        
        captured_transcript = None
        def callback(t):
            nonlocal captured_transcript
            captured_transcript = t
        self.runtime.on_transcription = callback
        
        self.runtime.stop_listening()
        self.assertEqual(self.runtime.state, VoiceState.PROCESSING)
        self.assertIsNotNone(captured_transcript)
        self.assertEqual(captured_transcript.text, "hello")
        self.assertFalse(self.cap._recording)

    def test_stop_listening_failure(self):
        self.runtime.start_listening()
        # force mock to fail
        self.cap._data = b'fail'
        
        with self.assertRaises(RuntimeError):
            self.runtime.stop_listening()
            
        self.assertEqual(self.runtime.state, VoiceState.IDLE)
        self.assertFalse(self.cap._recording)

    def test_speak(self):
        self.runtime.state_machine._state = VoiceState.PROCESSING
        self.runtime.speak("test output")
        # Since it's synchronous in this MVP, it ends in IDLE
        self.assertEqual(self.runtime.state, VoiceState.IDLE)

    def test_interrupt(self):
        self.runtime.state_machine._state = VoiceState.SPEAKING
        self.runtime.interrupt()
        self.assertEqual(self.runtime.state, VoiceState.LISTENING)
        self.assertTrue(self.cap._recording)

    def test_timeout(self):
        self.runtime.start_listening()
        self.runtime.timeout()
        self.assertEqual(self.runtime.state, VoiceState.IDLE)
        self.assertFalse(self.cap._recording)

if __name__ == '__main__':
    unittest.main()
