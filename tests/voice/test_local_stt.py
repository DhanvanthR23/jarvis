"""Tests for local Vosk STT."""
import unittest

from jarvis.voice.stt.interface import Transcript
from jarvis.voice.stt.local import VoskSTT


class TestVoskSTT(unittest.TestCase):
    def setUp(self):
        self.stt = VoskSTT()
        
    def test_transcribe_empty_audio(self):
        if not self.stt.is_available():
            self.skipTest("Vosk not installed")
        
        # Empty PCM audio
        audio = b'\x00' * 32000  # 1s silence
        result = self.stt.transcribe(audio)
        
        self.assertIsInstance(result, Transcript)
        self.assertEqual(result.text, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(len(result.audio_hash), 64)

if __name__ == '__main__':
    unittest.main()
