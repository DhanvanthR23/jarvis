"""Tests for local Kokoro TTS (G27.6)."""
import unittest

from jarvis.voice.audio import MockAudioPlayback
from jarvis.voice.tts.kokoro import KokoroTTS


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


class TestKokoroVoiceResolution(unittest.TestCase):
    def setUp(self):
        import os
        # Clean up environment before each test
        if "JARVIS_VOICE_NAME" in os.environ:
            del os.environ["JARVIS_VOICE_NAME"]

    def tearDown(self):
        import os
        if "JARVIS_VOICE_NAME" in os.environ:
            del os.environ["JARVIS_VOICE_NAME"]

    def test_cli_flag_wins(self):
        import os

        from jarvis.voice.tts.kokoro import resolve_kokoro_voice_name
        os.environ["JARVIS_VOICE_NAME"] = "am_michael"
        
        # CLI flag is 'am_onyx', should beat the env var 'am_michael'
        resolved = resolve_kokoro_voice_name("am_onyx")
        self.assertEqual(resolved, "am_onyx")

    def test_env_var_used_when_no_flag(self):
        import os

        from jarvis.voice.tts.kokoro import resolve_kokoro_voice_name
        os.environ["JARVIS_VOICE_NAME"] = "am_michael"
        
        # CLI flag is None
        resolved = resolve_kokoro_voice_name(None)
        self.assertEqual(resolved, "am_michael")

    def test_invalid_name_falls_back_with_warning(self):
        import io
        import sys

        from jarvis.voice.tts.kokoro import resolve_kokoro_voice_name
        
        # Capture stderr to check for the warning
        captured_stderr = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_stderr
        
        try:
            resolved = resolve_kokoro_voice_name("nonexistent_voice")
            self.assertEqual(resolved, "am_michael")
            self.assertIn("Warning: 'nonexistent_voice' is not a valid voice name", captured_stderr.getvalue())
        finally:
            sys.stderr = old_stderr

if __name__ == '__main__':
    unittest.main()
