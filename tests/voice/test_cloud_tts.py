"""Tests for G28: Cloud TTS via host-side proxy daemon.

Tests cover:
- IPC protocol (client ↔ daemon round-trip)
- Rate limiter (token-bucket, 500 words/minute)
- Fallback to Piper on timeout, error, and simulated network loss
- Fallback logging with timestamp and reason
- CloudTTS.is_available() checks
- Daemon lifecycle (start/stop/cleanup)
"""

import io
import json
import logging
import os
import socket
import struct
import tempfile
import threading
import time
import wave

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes(duration_s: float = 0.1, sample_rate: int = 24000) -> bytes:
    """Generate a short silent WAV for test assertions."""
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b'\x00\x00' * n_samples)
    return buf.getvalue()


def _ipc_request(sock_path: str, text: str) -> bytes:
    """Send a TTS request via IPC and return the response payload."""
    request = json.dumps({"text": text}).encode("utf-8")
    header = struct.pack("!I", len(request))

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect(sock_path)
    try:
        sock.sendall(header + request)

        raw_len = b''
        while len(raw_len) < 4:
            chunk = sock.recv(4 - len(raw_len))
            if not chunk:
                raise RuntimeError("Connection closed")
            raw_len += chunk

        resp_len = struct.unpack("!I", raw_len)[0]
        payload = b''
        while len(payload) < resp_len:
            chunk = sock.recv(resp_len - len(payload))
            if not chunk:
                raise RuntimeError("Connection closed")
            payload += chunk

        return payload
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Mock Piper for fallback testing (no real model needed)
# ---------------------------------------------------------------------------

class MockPiperTTS:
    """Minimal mock matching the PiperTTS interface used by the daemon."""

    def __init__(self):
        self._available = True
        self.speak_calls = []
        self._voice = self  # self acts as its own voice for synthesize_wav

    def is_available(self) -> bool:
        return self._available

    def _ensure_model(self):
        pass

    def synthesize_wav(self, text, wave_file):
        """Write a short silent WAV frame to the wave_file object."""
        self.speak_calls.append(text)
        wave_file.setnchannels(1)
        wave_file.setsampwidth(2)
        wave_file.setframerate(24000)
        wave_file.writeframes(b'\x00\x00' * 2400)  # 0.1s silence


class MockAudioPlayback:
    """Mock playback that records what was played."""

    def __init__(self):
        self.played = []
        self.stopped = False

    def play(self, audio: bytes) -> None:
        self.played.append(audio)

    def stop(self) -> None:
        self.stopped = True

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter Tests
# ---------------------------------------------------------------------------

class TestTokenBucketRateLimiter:
    def test_consume_within_capacity(self):
        from jarvis.voice.proxy.daemon import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=100, refill_rate=100 / 60.0)
        assert limiter.try_consume(50) is True
        assert limiter.try_consume(50) is True

    def test_consume_exceeds_capacity(self):
        from jarvis.voice.proxy.daemon import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=100, refill_rate=100 / 60.0)
        assert limiter.try_consume(101) is False

    def test_consume_drains_then_rejects(self):
        from jarvis.voice.proxy.daemon import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(capacity=100, refill_rate=100 / 60.0)
        assert limiter.try_consume(100) is True
        assert limiter.try_consume(1) is False

    def test_refill_restores_tokens(self):
        from jarvis.voice.proxy.daemon import TokenBucketRateLimiter
        # Very fast refill for testing: 1000 tokens/sec
        limiter = TokenBucketRateLimiter(capacity=100, refill_rate=1000.0)
        assert limiter.try_consume(100) is True
        time.sleep(0.15)  # Should refill ~150 tokens, capped at 100
        assert limiter.try_consume(50) is True

    def test_500_words_per_minute_default(self):
        from jarvis.voice.proxy.daemon import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter()  # defaults: capacity=500, rate=500/60
        assert limiter.try_consume(500) is True
        assert limiter.try_consume(1) is False


# ---------------------------------------------------------------------------
# Daemon IPC Protocol Tests
# ---------------------------------------------------------------------------

class TestDaemonIPC:
    """Test the daemon's IPC protocol using a mock Piper fallback.

    These tests force fallback (no real edge-tts call) to verify the
    IPC round-trip independently of network access.
    """

    @pytest.fixture
    def daemon_with_mock_piper(self, tmp_path):
        """Start a daemon configured to always fall back to mock Piper."""
        from jarvis.voice.proxy.daemon import TTSProxyDaemon

        sock_path = str(tmp_path / "test_tts.sock")
        mock_piper = MockPiperTTS()
        playback = MockAudioPlayback()

        daemon = TTSProxyDaemon(
            socket_path=sock_path,
            playback=playback,
            piper_tts=mock_piper,
        )
        daemon.start()
        time.sleep(0.2)  # Let the daemon bind

        yield daemon, mock_piper, playback, sock_path

        daemon.stop()

    def test_basic_round_trip(self, daemon_with_mock_piper, monkeypatch):
        daemon, mock_piper, playback, sock_path = daemon_with_mock_piper

        # Monkeypatch edge-tts to always raise (force fallback)
        import jarvis.voice.proxy.daemon as daemon_mod
        monkeypatch.setattr(
            daemon_mod, "synthesize_edge_tts_sync",
            lambda text, voice=None: (_ for _ in ()).throw(OSError("network down"))
        )

        payload = _ipc_request(sock_path, "Hello world")

        # Should be valid WAV (from mock Piper fallback)
        assert len(payload) > 44  # WAV header is 44 bytes
        assert payload[:4] == b'RIFF'
        assert len(mock_piper.speak_calls) == 1
        assert mock_piper.speak_calls[0] == "Hello world"

    def test_empty_text_returns_error(self, daemon_with_mock_piper):
        _, _, _, sock_path = daemon_with_mock_piper
        payload = _ipc_request(sock_path, "   ")
        result = json.loads(payload.decode("utf-8"))
        assert "error" in result
        assert "empty" in result["error"]

    def test_rate_limit_triggers_fallback(self, daemon_with_mock_piper, monkeypatch):
        daemon, mock_piper, playback, sock_path = daemon_with_mock_piper

        # Drain the rate limiter
        daemon._rate_limiter.try_consume(500)

        # Next request should be rate-limited → falls back to Piper
        payload = _ipc_request(sock_path, "one two three four five")

        # Should still get WAV (from Piper fallback)
        assert payload[:4] == b'RIFF'
        assert len(mock_piper.speak_calls) == 1


# ---------------------------------------------------------------------------
# Fallback Logging Tests
# ---------------------------------------------------------------------------

class TestFallbackLogging:
    """Verify that every fallback event is logged with timestamp + reason."""

    @pytest.fixture
    def daemon_and_logger(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon

        sock_path = str(tmp_path / "test_tts.sock")
        mock_piper = MockPiperTTS()
        playback = MockAudioPlayback()

        daemon = TTSProxyDaemon(
            socket_path=sock_path,
            playback=playback,
            piper_tts=mock_piper,
        )
        daemon.start()
        time.sleep(0.2)

        # Capture log output
        log_handler = logging.handlers_if_needed = []
        logger = logging.getLogger("jarvis.voice.proxy")
        handler = logging.StreamHandler(io.StringIO())
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        yield daemon, mock_piper, sock_path, handler

        daemon.stop()
        logger.removeHandler(handler)

    def test_timeout_fallback_logged(self, daemon_and_logger, monkeypatch):
        daemon, mock_piper, sock_path, handler = daemon_and_logger
        import asyncio
        import jarvis.voice.proxy.daemon as daemon_mod

        def fake_timeout(text, voice=None):
            raise asyncio.TimeoutError()

        monkeypatch.setattr(daemon_mod, "synthesize_edge_tts_sync", fake_timeout)

        _ipc_request(sock_path, "test timeout")

        log_output = handler.stream.getvalue()
        assert "FALLBACK" in log_output
        assert "timeout" in log_output

    def test_network_error_fallback_logged(self, daemon_and_logger, monkeypatch):
        daemon, mock_piper, sock_path, handler = daemon_and_logger
        import jarvis.voice.proxy.daemon as daemon_mod

        def fake_network_error(text, voice=None):
            raise OSError("Network is unreachable")

        monkeypatch.setattr(daemon_mod, "synthesize_edge_tts_sync", fake_network_error)

        _ipc_request(sock_path, "test network")

        log_output = handler.stream.getvalue()
        assert "FALLBACK" in log_output
        assert "network_error" in log_output

    def test_edge_tts_error_fallback_logged(self, daemon_and_logger, monkeypatch):
        daemon, mock_piper, sock_path, handler = daemon_and_logger
        import jarvis.voice.proxy.daemon as daemon_mod

        def fake_edge_error(text, voice=None):
            raise RuntimeError("edge-tts protocol changed")

        monkeypatch.setattr(daemon_mod, "synthesize_edge_tts_sync", fake_edge_error)

        _ipc_request(sock_path, "test edge error")

        log_output = handler.stream.getvalue()
        assert "FALLBACK" in log_output
        assert "edge_tts_error" in log_output

    def test_rate_limit_fallback_logged(self, daemon_and_logger):
        daemon, mock_piper, sock_path, handler = daemon_and_logger

        # Drain the rate limiter
        daemon._rate_limiter.try_consume(500)

        _ipc_request(sock_path, "rate limited text here")

        log_output = handler.stream.getvalue()
        assert "FALLBACK" in log_output
        assert "rate_limit" in log_output


# ---------------------------------------------------------------------------
# CloudTTS Client Tests
# ---------------------------------------------------------------------------

class TestCloudTTS:
    def test_is_available_no_socket(self, tmp_path):
        from jarvis.voice.tts.cloud import CloudTTS
        playback = MockAudioPlayback()
        tts = CloudTTS(playback, socket_path=str(tmp_path / "nonexistent.sock"))
        assert tts.is_available() is False

    def test_is_available_with_daemon(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        from jarvis.voice.tts.cloud import CloudTTS

        sock_path = str(tmp_path / "test.sock")
        playback = MockAudioPlayback()
        mock_piper = MockPiperTTS()

        daemon = TTSProxyDaemon(
            socket_path=sock_path,
            playback=playback,
            piper_tts=mock_piper,
        )
        daemon.start()
        time.sleep(0.2)

        try:
            tts = CloudTTS(playback, socket_path=sock_path)
            assert tts.is_available() is True
        finally:
            daemon.stop()

    def test_speak_plays_audio(self, tmp_path, monkeypatch):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        from jarvis.voice.tts.cloud import CloudTTS
        import jarvis.voice.proxy.daemon as daemon_mod

        # Force fallback to Piper
        monkeypatch.setattr(
            daemon_mod, "synthesize_edge_tts_sync",
            lambda text, voice=None: (_ for _ in ()).throw(OSError("no net"))
        )

        sock_path = str(tmp_path / "test.sock")
        playback = MockAudioPlayback()
        mock_piper = MockPiperTTS()

        daemon = TTSProxyDaemon(
            socket_path=sock_path,
            playback=playback,
            piper_tts=mock_piper,
        )
        daemon.start()
        time.sleep(0.2)

        try:
            tts = CloudTTS(playback, socket_path=sock_path)
            tts.speak("Hello from cloud TTS")

            assert len(playback.played) == 1
            assert playback.played[0][:4] == b'RIFF'
        finally:
            daemon.stop()

    def test_speak_empty_text_noop(self, tmp_path):
        from jarvis.voice.tts.cloud import CloudTTS
        playback = MockAudioPlayback()
        tts = CloudTTS(playback, socket_path=str(tmp_path / "dummy.sock"))
        # Should not raise, should not connect
        tts.speak("")
        tts.speak("   ")
        assert len(playback.played) == 0

    def test_stop_delegates_to_playback(self, tmp_path):
        from jarvis.voice.tts.cloud import CloudTTS
        playback = MockAudioPlayback()
        tts = CloudTTS(playback, socket_path=str(tmp_path / "dummy.sock"))
        tts.stop()
        assert playback.stopped is True


# ---------------------------------------------------------------------------
# Daemon Lifecycle Tests
# ---------------------------------------------------------------------------

class TestDaemonLifecycle:
    def test_start_creates_socket(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        sock_path = str(tmp_path / "lifecycle.sock")
        daemon = TTSProxyDaemon(socket_path=sock_path)
        daemon.start()
        try:
            assert os.path.exists(sock_path)
        finally:
            daemon.stop()

    def test_stop_removes_socket(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        sock_path = str(tmp_path / "lifecycle.sock")
        daemon = TTSProxyDaemon(socket_path=sock_path)
        daemon.start()
        time.sleep(0.1)
        daemon.stop()
        assert not os.path.exists(sock_path)

    def test_double_start_is_safe(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        sock_path = str(tmp_path / "lifecycle.sock")
        daemon = TTSProxyDaemon(socket_path=sock_path)
        daemon.start()
        daemon.start()  # Should not raise
        daemon.stop()

    def test_stale_socket_cleaned_up(self, tmp_path):
        from jarvis.voice.proxy.daemon import TTSProxyDaemon
        sock_path = str(tmp_path / "lifecycle.sock")
        # Create a stale socket file
        with open(sock_path, 'w') as f:
            f.write("stale")

        daemon = TTSProxyDaemon(socket_path=sock_path)
        daemon.start()
        time.sleep(0.1)
        try:
            # Should have replaced the stale file with a real socket
            assert os.path.exists(sock_path)
        finally:
            daemon.stop()
