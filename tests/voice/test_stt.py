"""Tests for STT/TTS interfaces (plan2.md sections 8, 12)."""
import unittest

from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech


class MockSTT(SpeechToText):
    def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(
            text="test",
            confidence=0.95,
            audio_hash=Transcript.compute_audio_hash(audio),
        )
    def is_available(self) -> bool:
        return True


class MockTTS(TextToSpeech):
    def __init__(self):
        self.spoken = []
        self.stopped = False
    def speak(self, text: str) -> None:
        self.spoken.append(text)
    def stop(self) -> None:
        self.stopped = True
    def is_available(self) -> bool:
        return True


class TestSTTInterface(unittest.TestCase):

    def test_transcribe_returns_transcript(self):
        stt = MockSTT()
        t = stt.transcribe(b"audio data")
        self.assertIsInstance(t, Transcript)
        self.assertEqual(t.text, "test")
        self.assertGreater(t.confidence, 0.0)

    def test_audio_hash_computed(self):
        stt = MockSTT()
        t = stt.transcribe(b"audio data")
        self.assertTrue(len(t.audio_hash) == 64)  # SHA-256 hex

    def test_transcript_is_frozen(self):
        t = Transcript(text="x", confidence=0.9)
        with self.assertRaises(AttributeError):
            t.text = "modified"

    def test_is_available(self):
        self.assertTrue(MockSTT().is_available())


class TestTTSInterface(unittest.TestCase):

    def test_speak(self):
        tts = MockTTS()
        tts.speak("hello")
        self.assertEqual(tts.spoken, ["hello"])

    def test_stop(self):
        tts = MockTTS()
        tts.stop()
        self.assertTrue(tts.stopped)

    def test_is_available(self):
        self.assertTrue(MockTTS().is_available())


if __name__ == '__main__':
    unittest.main()
