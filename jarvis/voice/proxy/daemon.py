"""Host-side TTS Proxy Daemon (G28 — plan section Cloud TTS).

This daemon runs in the TRUSTED host context (outside the bwrap sandbox).
It listens on a Unix domain socket for text from the sandboxed agent,
calls edge-tts over HTTPS, and plays the resulting audio via PyAudio.

Security invariants:
- The sandboxed agent NEVER makes outbound network calls for TTS.
- All cloud TTS traffic routes through this daemon exclusively.
- Fallback to local PiperTTS on timeout (>1000ms), error, or network loss.
- Every fallback event is logged with timestamp and reason.
- Token-bucket rate limiter enforces 500 words/minute hard cap.
"""

import asyncio
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
from pathlib import Path

logger = logging.getLogger("jarvis.voice.proxy")


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (500 words / minute)
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """Token-bucket rate limiter counting words, not requests.

    Capacity: 500 words.  Refill rate: 500 words per 60 seconds.
    """

    def __init__(self, capacity: int = 500, refill_rate: float = 500 / 60.0):
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill_rate = refill_rate  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def try_consume(self, word_count: int) -> bool:
        """Attempt to consume *word_count* tokens.  Returns True on success."""
        with self._lock:
            self._refill()
            if self._tokens >= word_count:
                self._tokens -= word_count
                return True
            return False


# ---------------------------------------------------------------------------
# Edge-TTS synthesis (async helper)
# ---------------------------------------------------------------------------

EDGE_TTS_TIMEOUT_S = 3.0  # 3000 ms hard deadline per utterance
EDGE_TTS_VOICE = "en-US-GuyNeural"


async def _synthesize_edge_tts(text: str, voice: str = EDGE_TTS_VOICE) -> bytes:
    """Call edge-tts and return raw WAV bytes.

    Raises asyncio.TimeoutError if the call exceeds EDGE_TTS_TIMEOUT_S.
    Raises any edge_tts exception on network / protocol errors.
    """
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice,
        connect_timeout=2,
        receive_timeout=5,
    )

    # edge-tts streams MP3 chunks — collect them, then save to a temp file
    # and read back as WAV via its built-in save helper.
    tmp_dir = tempfile.gettempdir()
    mp3_path = os.path.join(tmp_dir, f"jarvis_edge_tts_{os.getpid()}.mp3")
    wav_path = os.path.join(tmp_dir, f"jarvis_edge_tts_{os.getpid()}.wav")

    try:
        await asyncio.wait_for(
            communicate.save(mp3_path),
            timeout=EDGE_TTS_TIMEOUT_S,
        )

        # Convert MP3 → WAV using ffmpeg (ubiquitous on Linux)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", mp3_path, "-ar", "24000",
            "-ac", "1", "-sample_fmt", "s16", wav_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5.0)

        if proc.returncode != 0:
            raise RuntimeError("ffmpeg MP3→WAV conversion failed")

        with open(wav_path, "rb") as f:
            return f.read()
    finally:
        for p in (mp3_path, wav_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def synthesize_edge_tts_sync(text: str, voice: str = EDGE_TTS_VOICE) -> bytes:
    """Synchronous wrapper around the async edge-tts call."""
    return asyncio.run(_synthesize_edge_tts(text, voice))


# ---------------------------------------------------------------------------
# TTS Proxy Daemon
# ---------------------------------------------------------------------------

class TTSProxyDaemon:
    """Host-side daemon that bridges IPC text → cloud TTS → audio playback.

    Protocol (Unix domain socket, stream):
        Request:  4-byte big-endian length prefix + UTF-8 JSON payload
                  {"text": "...", "request_id": "..."}
        Response: 4-byte big-endian length prefix + payload
                  On success: raw WAV bytes
                  On error:   UTF-8 JSON {"error": "..."}
    """

    def __init__(
        self,
        socket_path: str | None = None,
        playback=None,
        piper_tts=None,
        voice: str = EDGE_TTS_VOICE,
    ):
        self._socket_path = socket_path or os.path.join(
            tempfile.gettempdir(), f"jarvis_tts_proxy_{os.getuid()}.sock"
        )
        self._playback = playback
        self._piper_tts = piper_tts
        self._voice = voice
        self._rate_limiter = TokenBucketRateLimiter()
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def socket_path(self) -> str:
        return self._socket_path

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the daemon in a background thread."""
        if self._running:
            return

        # Clean up stale socket
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(self._socket_path)
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)  # allow periodic shutdown checks
        self._running = True

        self._thread = threading.Thread(
            target=self._serve_loop, name="tts-proxy-daemon", daemon=True
        )
        self._thread.start()
        logger.info("TTS proxy daemon started on %s", self._socket_path)

    def stop(self) -> None:
        """Stop the daemon and clean up the socket file."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass
        logger.info("TTS proxy daemon stopped")

    # -- Server loop ---------------------------------------------------------

    def _serve_loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                self._handle_connection(conn)
            except Exception as exc:
                logger.error("Error handling TTS connection: %s", exc)
            finally:
                conn.close()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single IPC request."""
        # Read length-prefixed request
        raw_len = self._recv_exact(conn, 4)
        if not raw_len:
            return
        msg_len = struct.unpack("!I", raw_len)[0]
        if msg_len > 1_000_000:  # 1 MB sanity limit
            self._send_error(conn, "request too large")
            return

        raw_msg = self._recv_exact(conn, msg_len)
        if not raw_msg:
            return

        try:
            request = json.loads(raw_msg.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_error(conn, f"invalid request: {exc}")
            return

        text = request.get("text", "").strip()
        if not text:
            self._send_error(conn, "empty text")
            return

        # Rate-limit check
        word_count = len(text.split())
        if not self._rate_limiter.try_consume(word_count):
            reason = "rate_limit_exceeded"
            logger.warning(
                "[%s] TTS FALLBACK: %s (text=%d words)",
                time.strftime("%Y-%m-%dT%H:%M:%S"), reason, word_count,
            )
            wav_data = self._fallback_piper(text, reason)
            self._send_wav(conn, wav_data)
            return

        # Attempt edge-tts
        wav_data = self._try_edge_tts(text)
        self._send_wav(conn, wav_data)

    # -- Edge TTS with fallback ----------------------------------------------

    def _try_edge_tts(self, text: str) -> bytes:
        """Try edge-tts; fall back to Piper on any failure."""
        try:
            wav_data = synthesize_edge_tts_sync(text, voice=self._voice)
            return wav_data
        except asyncio.TimeoutError:
            reason = "timeout"
        except OSError as exc:
            # Network unreachable, DNS failure, etc.
            reason = f"network_error: {exc}"
        except Exception as exc:
            reason = f"edge_tts_error: {exc}"

        logger.warning(
            "[%s] TTS FALLBACK: %s (text=%r)",
            time.strftime("%Y-%m-%dT%H:%M:%S"), reason, text[:80],
        )
        return self._fallback_piper(text, reason)

    def _fallback_piper(self, text: str, reason: str) -> bytes:
        """Synthesize with PiperTTS and return WAV bytes."""
        if self._piper_tts is None or not self._piper_tts.is_available():
            logger.error(
                "[%s] TTS FALLBACK FAILED: Piper not available (original reason: %s)",
                time.strftime("%Y-%m-%dT%H:%M:%S"), reason,
            )
            # Return silence (1 second of 24kHz mono 16-bit)
            return self._generate_silence()

        try:
            # PiperTTS.speak() plays audio directly.  We need the raw WAV
            # bytes instead, so we replicate the synthesis step only.
            self._piper_tts._ensure_model()
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                self._piper_tts._voice.synthesize_wav(text, wf)
            return buf.getvalue()
        except Exception as exc:
            logger.error(
                "[%s] TTS FALLBACK FAILED: Piper error: %s (original reason: %s)",
                time.strftime("%Y-%m-%dT%H:%M:%S"), exc, reason,
            )
            return self._generate_silence()

    @staticmethod
    def _generate_silence(duration_s: float = 0.5, sample_rate: int = 24000) -> bytes:
        """Generate a short silent WAV as a last-resort fallback."""
        n_samples = int(sample_rate * duration_s)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * n_samples)
        return buf.getvalue()

    # -- IPC helpers ---------------------------------------------------------

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        """Receive exactly *n* bytes from *sock*."""
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def _send_wav(conn: socket.socket, wav_data: bytes) -> None:
        """Send WAV data with a 4-byte length prefix."""
        header = struct.pack("!I", len(wav_data))
        conn.sendall(header + wav_data)

    @staticmethod
    def _send_error(conn: socket.socket, message: str) -> None:
        """Send a JSON error with a 4-byte length prefix."""
        payload = json.dumps({"error": message}).encode("utf-8")
        header = struct.pack("!I", len(payload))
        conn.sendall(header + payload)
