"""Tests for local Kokoro TTS (G27.6)."""
import unittest
from jarvis.voice.tts.kokoro import KokoroTTS
from jarvis.voice.audio import MockAudioPlayback

class TestKokoroTTS(unittest.TestCase):
    def setUp(self):
        self.playback = MockAudioPlayback()
        self.tts = KokoroTTS(playback=self.playback)
        
    def test_speak(self):
        if not self.tts.is_available():
            self.skipTest("Kokoro not installed")
            
        try:
            self.tts.speak("Hello Jarvis")
            self.assertEqual(len(self.playback.played), 1)
            # Should be a WAV file
            self.assertTrue(self.playback.played[0].startswith(b'RIFF'))
        except FileNotFoundError:
            # If the model files don't exist, our mock fallback should kick in
            self.assertEqual(len(self.playback.played), 1)
            self.assertTrue(self.playback.played[0].startswith(b'RIFF'))

    def test_stop(self):
        if not self.tts.is_available():
            self.skipTest("Kokoro not installed")
            
        self.tts.stop()
        self.assertTrue(self.playback.stopped)

if __name__ == '__main__':
    unittest.main()
