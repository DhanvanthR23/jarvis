"""Tests for audio abstraction (G24.2)."""
import unittest

from jarvis.voice.audio import AudioChunk, MockAudioCapture, MockAudioPlayback


class TestAudioChunk(unittest.TestCase):

    def test_duration_seconds(self):
        # 32000 bytes at 16kHz, mono, 16-bit = 1 second
        chunk = AudioChunk(data=b'\x00' * 32000, sample_rate=16000, channels=1, sample_width=2)
        self.assertAlmostEqual(chunk.duration_seconds, 1.0)

    def test_audio_hash_deterministic(self):
        data = b'test audio'
        c1 = AudioChunk(data=data)
        c2 = AudioChunk(data=data)
        self.assertEqual(c1.audio_hash(), c2.audio_hash())
        self.assertEqual(len(c1.audio_hash()), 64)

    def test_to_wav_starts_with_riff(self):
        chunk = AudioChunk(data=b'\x00' * 100)
        wav = chunk.to_wav()
        self.assertTrue(wav.startswith(b'RIFF'))
        self.assertIn(b'WAVE', wav[:12])

    def test_empty_data_zero_duration(self):
        chunk = AudioChunk(data=b'', sample_rate=16000)
        self.assertEqual(chunk.duration_seconds, 0.0)


class TestMockAudioCapture(unittest.TestCase):

    def test_capture_cycle(self):
        cap = MockAudioCapture()
        self.assertTrue(cap.is_available())
        cap.start()
        chunk = cap.stop()
        self.assertIsInstance(chunk, AudioChunk)
        self.assertGreater(len(chunk.data), 0)

    def test_data_cleared_after_stop(self):
        cap = MockAudioCapture()
        cap.start()
        cap.stop()
        # Second stop returns empty
        chunk2 = cap.stop()
        self.assertEqual(len(chunk2.data), 0)


class TestMockAudioPlayback(unittest.TestCase):

    def test_playback(self):
        pb = MockAudioPlayback()
        self.assertTrue(pb.is_available())
        pb.play(b'audio')
        self.assertEqual(pb.played, [b'audio'])

    def test_stop(self):
        pb = MockAudioPlayback()
        pb.stop()
        self.assertTrue(pb.stopped)


if __name__ == '__main__':
    unittest.main()
