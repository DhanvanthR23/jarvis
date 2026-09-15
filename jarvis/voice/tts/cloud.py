"""Cloud TTS implementation via host-side proxy (G28).

This is the AGENT-SIDE client.  It implements the TextToSpeech ABC but
does NOT make any network calls.  Instead it sends text over a Unix
domain socket to the trusted host-side TTSProxyDaemon, which performs
the actual edge-tts call and returns WAV audio for playback.

Security invariant: this class NEVER imports edge_tts or opens any
network connection.  All cloud traffic is proxied through the daemon.
"""

import json
import logging
import socket
import struct

from jarvis.voice.audio import AudioPlayback
from jarvis.voice.tts.interface import TextToSpeech

logger = logging.getLogger("jarvis.voice.tts.cloud")


class CloudTTS(TextToSpeech):
    """Cloud TTS via the host-side proxy daemon (edge-tts).

    The sandboxed agent only writes text to a local Unix domain socket.
    Audio playback is handled on the host side after receiving WAV bytes
    back through the same socket.
    """

    def __init__(self, playback: AudioPlayback, socket_path: str):
        self._playback = playback
        self._socket_path = socket_path
        self._available = True  # Availability depends on daemon being up
        self._stopped = False
        self._active_sock: socket.socket | None = None

    def is_available(self) -> bool:
        """Check if the proxy daemon socket exists and is connectable."""
        try:
            import os
            if not os.path.exists(self._socket_path):
                return False
            # Attempt a quick connect to verify daemon is alive
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect(self._socket_path)
            sock.close()
            return True
        except (OSError, socket.error):
            return False

    def speak(self, text: str) -> None:
        """Send text to the proxy daemon and play the returned audio.

        The daemon handles:
        - edge-tts synthesis (cloud call)
        - Fallback to Piper on timeout/error/network loss
        - Rate limiting (500 words/minute)
        - Logging of all fallback events

        This method never makes network calls itself.
        """
        self._stopped = False
        if not text.strip():
            return

        if not self._playback.is_available():
            raise RuntimeError("Audio playback is not available")

        try:
            wav_data = self._request_synthesis(text)
            if self._stopped:
                return
            self._playback.play(wav_data)
        except (TimeoutError, OSError) as exc:
            if self._stopped:
                return  # Interrupted — suppress socket errors silently
            logger.error("CloudTTS.speak failed: %s", exc)
            raise
        except Exception as exc:
            logger.error("CloudTTS.speak failed: %s", exc)
            raise

    def stop(self) -> None:
        """Stop playback immediately and abort any in-flight synthesis."""
        self._stopped = True
        # Shut down the active socket to unblock _recv_exact immediately
        sock = self._active_sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._playback.stop()

    def _request_synthesis(self, text: str) -> bytes:
        """Send text to the daemon and receive WAV bytes back.

        Protocol:
            Send:    4-byte big-endian length + UTF-8 JSON {"text": "..."}
            Receive: 4-byte big-endian length + WAV bytes (or JSON error)
        """
        request = json.dumps({"text": text}).encode("utf-8")
        header = struct.pack("!I", len(request))

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10.0)  # generous overall timeout; daemon enforces 1s internally
        self._active_sock = sock
        try:
            sock.connect(self._socket_path)
            sock.sendall(header + request)

            # Read response length
            raw_len = self._recv_exact(sock, 4)
            if not raw_len:
                raise RuntimeError("Daemon closed connection without response")
            resp_len = struct.unpack("!I", raw_len)[0]

            if resp_len > 50_000_000:  # 50 MB sanity limit
                raise RuntimeError(f"Response too large: {resp_len} bytes")

            # Read response payload
            payload = self._recv_exact(sock, resp_len)
            if not payload:
                raise RuntimeError("Daemon closed connection during response")

            # Check if it's a JSON error
            if payload[:1] == b'{':
                try:
                    error_msg = json.loads(payload.decode("utf-8"))
                    if "error" in error_msg:
                        raise RuntimeError(f"Daemon error: {error_msg['error']}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # Not JSON — treat as WAV data

            return payload
        finally:
            self._active_sock = None
            sock.close()

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
