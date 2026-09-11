"""Tests for local faster-whisper STT (G27.6)."""
import unittest

from jarvis.voice.stt.faster_whisper import FasterWhisperSTT
from jarvis.voice.stt.interface import Transcript


class TestFasterWhisperSTT(unittest.TestCase):
    def setUp(self):
        self.stt = FasterWhisperSTT()
        
    def test_transcribe_empty_audio(self):
        if not self.stt.is_available():
            self.skipTest("faster-whisper not installed")
        
        # Empty PCM audio
        audio = b'\x00' * 32000  # 1s silence
        result = self.stt.transcribe(audio)
        
        self.assertIsInstance(result, Transcript)
        # Empty audio usually results in empty string or a halluciation like " [BLANK_AUDIO] "
        # Confidence should be low.
        self.assertTrue(result.confidence <= 1.0)
        self.assertTrue(result.confidence >= 0.0)
        self.assertEqual(len(result.audio_hash), 64)

if __name__ == '__main__':
    unittest.main()
