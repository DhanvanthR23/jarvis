#!/usr/bin/env python3
"""G28 Cloud TTS Benchmark — Edge TTS via host-side proxy.

Measures cold-start and steady-state (5 runs) latency using the same test
sentence format as the MeloTTS and sherpa-onnx benchmarks for comparability.

Reports:
  - Cold-start latency (first synthesis including daemon startup + edge-tts
    connection establishment)
  - Steady-state latency (5 consecutive runs: min, max, mean)
  - Total WAV bytes received per utterance

Usage:
    .venv/bin/python tests/benchmarks/cloud_tts_benchmark.py

Requires network access and edge-tts==7.2.8 installed.
"""

import io
import json
import os
import socket
import struct
import sys
import time
import wave

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


TEST_SENTENCE = (
    "The quick brown fox jumps over the lazy dog. "
    "This is a benchmark sentence for measuring text to speech latency."
)

NUM_STEADY_STATE_RUNS = 5


def ipc_request(sock_path: str, text: str) -> tuple[bytes, float]:
    """Send a TTS request via IPC. Returns (wav_bytes, elapsed_seconds)."""
    request = json.dumps({"text": text}).encode("utf-8")
    header = struct.pack("!I", len(request))

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30.0)
    sock.connect(sock_path)

    t0 = time.monotonic()
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

        elapsed = time.monotonic() - t0
        return payload, elapsed
    finally:
        sock.close()


def wav_duration_s(wav_data: bytes) -> float:
    """Get the duration of WAV audio in seconds."""
    try:
        with wave.open(io.BytesIO(wav_data), 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate else 0.0
    except Exception:
        return 0.0


def main():
    print("=" * 60)
    print("G28 Cloud TTS Benchmark — Edge TTS via Host-Side Proxy")
    print("=" * 60)

    # Machine info
    model_name = os.popen('lscpu | grep "Model name"').read().strip()
    print(f"Machine: {model_name}")
    print(f"Test sentence: {TEST_SENTENCE!r}")
    print(f"Steady-state runs: {NUM_STEADY_STATE_RUNS}")
    print()

    # Start daemon
    from jarvis.voice.audio import MockAudioPlayback
    from jarvis.voice.proxy.daemon import TTSProxyDaemon

    playback = MockAudioPlayback()

    # We don't need real Piper for benchmarking — we want to measure
    # edge-tts performance.  If edge-tts fails, the benchmark should
    # report that, not silently fall back.
    daemon = TTSProxyDaemon(playback=playback, piper_tts=None)

    print("Starting TTS proxy daemon...")
    t_daemon_start = time.monotonic()
    daemon.start()
    daemon_startup_ms = (time.monotonic() - t_daemon_start) * 1000
    print(f"  Daemon startup: {daemon_startup_ms:.1f} ms")
    print(f"  Socket: {daemon.socket_path}")
    print()

    try:
        # --- Cold start ---
        print("--- Cold Start ---")
        wav_data, elapsed = ipc_request(daemon.socket_path, TEST_SENTENCE)

        if wav_data[:4] == b'RIFF':
            duration = wav_duration_s(wav_data)
            print(f"  Latency:       {elapsed * 1000:.0f} ms")
            print(f"  WAV size:      {len(wav_data):,} bytes")
            print(f"  Audio length:  {duration:.2f} s")
            cold_start_ms = elapsed * 1000
        else:
            # Might be a JSON error
            try:
                err = json.loads(wav_data.decode())
                print(f"  ERROR: {err}")
            except Exception:
                print(f"  ERROR: unexpected response ({len(wav_data)} bytes)")
            cold_start_ms = None

        # --- Steady state ---
        print(f"\n--- Steady State ({NUM_STEADY_STATE_RUNS} runs) ---")
        latencies = []
        for i in range(NUM_STEADY_STATE_RUNS):
            wav_data, elapsed = ipc_request(daemon.socket_path, TEST_SENTENCE)
            ms = elapsed * 1000

            if wav_data[:4] == b'RIFF':
                duration = wav_duration_s(wav_data)
                print(f"  Run {i + 1}: {ms:.0f} ms  ({len(wav_data):,} bytes, {duration:.2f}s audio)")
                latencies.append(ms)
            else:
                print(f"  Run {i + 1}: ERROR")

        # --- Summary ---
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        if cold_start_ms is not None:
            print(f"  Cold start:         {cold_start_ms:.0f} ms")

        if latencies:
            print(f"  Steady-state min:   {min(latencies):.0f} ms")
            print(f"  Steady-state max:   {max(latencies):.0f} ms")
            print(f"  Steady-state mean:  {sum(latencies) / len(latencies):.0f} ms")
        else:
            print("  Steady-state:       ALL FAILED")

        # Verdict
        print()
        if latencies and (sum(latencies) / len(latencies)) < 2000:
            print("  VERDICT:  PASS — mean latency under 2s threshold")
        elif latencies:
            print("  VERDICT:   MARGINAL — mean latency above 2s")
        else:
            print("  VERDICT:  FAIL — no successful synthesis")

    finally:
        daemon.stop()
        print("\nDaemon stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
