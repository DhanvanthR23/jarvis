"""Tests for local Piper TTS."""
import unittest
from jarvis.voice.tts.local import PiperTTS
from jarvis.voice.audio import MockAudioPlayback

class TestPiperTTS(unittest.TestCase):
    def setUp(self):
        self.playback = MockAudioPlayback()
        self.tts = PiperTTS(playback=self.playback)
        
    def test_speak(self):
        if not self.tts.is_available():
            self.skipTest("Piper not installed")
            
        self.tts.speak("Hello Jarvis")
        self.assertEqual(len(self.playback.played), 1)
        # Should be a WAV file
        self.assertTrue(self.playback.played[0].startswith(b'RIFF'))

    def test_stop(self):
        if not self.tts.is_available():
            self.skipTest("Piper not installed")
            
        self.tts.stop()
        self.assertTrue(self.playback.stopped)

if __name__ == '__main__':
    unittest.main()
