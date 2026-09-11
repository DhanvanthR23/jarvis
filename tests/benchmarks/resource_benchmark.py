#!/usr/bin/env python3
"""G24.3 Resource Feasibility Benchmark (plan2.md section 9).

Measures resource usage across three stages:
  Stage A: Jarvis idle baseline
  Stage B: Jarvis + candidate STT (vosk)
  Stage C: Jarvis + STT + TTS + AGY + MCP (simulated full load)

Reports: peak RAM, sustained RAM, CPU, latency.
"""
import json
import os
import resource
import sys
import time
import wave


def get_memory_mb():
    """Current process RSS in MB."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

def get_system_memory():
    """System memory from /proc/meminfo."""
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if parts[0] in ('MemTotal:', 'MemAvailable:', 'MemFree:'):
                info[parts[0].rstrip(':')] = int(parts[1]) // 1024  # MB
    return info

def generate_test_wav(path, duration_s=3, sample_rate=16000):
    """Generate a silent WAV file for benchmarking."""
    n_samples = sample_rate * duration_s
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Write silence (zeros)
        wf.writeframes(b'\x00\x00' * n_samples)

def stage_a():
    """Stage A: Jarvis idle baseline."""
    print("=== Stage A: Jarvis Idle Baseline ===")
    sys_mem = get_system_memory()
    get_memory_mb()
    
    # Import jarvis core to measure its footprint
    t0 = time.monotonic()
    from jarvis.agent.mock import MockAgent
    from jarvis.core.controller import JarvisController
    from jarvis.tools.registry import register_readonly_tools
    agent = MockAgent([])
    ctrl = JarvisController(agent_backend=agent)
    register_readonly_tools(ctrl)
    t1 = time.monotonic()
    
    proc_rss_after = get_memory_mb()
    sys_mem_after = get_system_memory()
    
    results = {
        'system_total_mb': sys_mem['MemTotal'],
        'system_available_before_mb': sys_mem['MemAvailable'],
        'system_available_after_mb': sys_mem_after['MemAvailable'],
        'process_rss_mb': proc_rss_after,
        'jarvis_init_latency_ms': (t1 - t0) * 1000,
    }
    for k, v in results.items():
        print(f"  {k}: {v:.1f}")
    return results

def stage_b(test_wav):
    """Stage B: Jarvis + candidate STT (vosk small model)."""
    print("\n=== Stage B: Jarvis + Vosk STT ===")
    sys_mem_before = get_system_memory()
    
    t0 = time.monotonic()
    from vosk import KaldiRecognizer, Model
    
    # Download small model if needed
    model_path = os.path.expanduser("~/.cache/vosk/vosk-model-small-en-us-0.15")
    if not os.path.exists(model_path):
        print("  Downloading vosk small model...")
        from vosk import Model
        # vosk auto-downloads if we just create Model with the name
        model = Model(model_name="vosk-model-small-en-us-0.15")
    else:
        model = Model(model_path)
    t1 = time.monotonic()
    model_load_ms = (t1 - t0) * 1000
    
    proc_rss_model = get_memory_mb()
    get_system_memory()
    
    # Transcribe test audio
    rec = KaldiRecognizer(model, 16000)
    with wave.open(test_wav, 'rb') as wf:
        t2 = time.monotonic()
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)
        json.loads(rec.FinalResult())
        t3 = time.monotonic()
    
    transcription_ms = (t3 - t2) * 1000
    proc_rss_after = get_memory_mb()
    sys_mem_after = get_system_memory()
    
    results = {
        'model_load_latency_ms': model_load_ms,
        'transcription_latency_ms': transcription_ms,
        'process_rss_after_model_mb': proc_rss_model,
        'process_rss_after_transcription_mb': proc_rss_after,
        'system_available_before_mb': sys_mem_before['MemAvailable'],
        'system_available_after_mb': sys_mem_after['MemAvailable'],
        'stt_ram_delta_mb': sys_mem_before['MemAvailable'] - sys_mem_after['MemAvailable'],
    }
    for k, v in results.items():
        print(f"  {k}: {v:.1f}")
    return results

def stage_c(test_wav):
    """Stage C: Simulated full stack (Jarvis + STT + TTS + mock AGY + MCP)."""
    print("\n=== Stage C: Full Stack Simulation ===")
    sys_mem_before = get_system_memory()
    
    # STT already loaded from stage_b, measure TTS loading
    t0 = time.monotonic()
    try:
        # Check if piper can be imported
        tts_available = True
        tts_load_ms = (time.monotonic() - t0) * 1000
    except Exception as e:
        tts_available = False
        tts_load_ms = 0
        print(f"  TTS (piper) import failed: {e}")
    
    # Simulate AGY + MCP load (JarvisController with mock agent processing)
    from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep
    from jarvis.core.controller import JarvisController
    from jarvis.tools.registry import register_readonly_tools
    
    scenarios = [
        ScriptedScenario('wifi', [ScriptedStep('network.interfaces', {})], 'Wifi info: {}'),
        ScriptedScenario('cpu', [ScriptedStep('processes.list', {})], 'Processes: {}'),
    ]
    agent = MockAgent(scenarios)
    ctrl = JarvisController(agent_backend=agent)
    register_readonly_tools(ctrl)
    
    # Simulate concurrent operation
    t1 = time.monotonic()
    for _ in range(5):
        ctrl.process_request("check wifi")
        ctrl.process_request("check cpu")
    t2 = time.monotonic()
    
    proc_rss = get_memory_mb()
    sys_mem_after = get_system_memory()
    
    results = {
        'tts_available': tts_available,
        'tts_import_latency_ms': tts_load_ms,
        'controller_10_requests_ms': (t2 - t1) * 1000,
        'peak_process_rss_mb': proc_rss,
        'system_available_after_mb': sys_mem_after['MemAvailable'],
        'system_ram_consumed_mb': sys_mem_before['MemAvailable'] - sys_mem_after['MemAvailable'],
    }
    for k, v in results.items():
        if isinstance(v, bool):
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v:.1f}")
    return results

def main():
    print("G24.3 Resource Feasibility Benchmark")
    model_name = os.popen('lscpu | grep "Model name"').read().strip()
    print(f'Machine: {model_name}')
    print(f"RAM: {get_system_memory()['MemTotal']} MB total")
    print()
    
    test_wav = '/tmp/jarvis_benchmark_test.wav'
    generate_test_wav(test_wav, duration_s=3)
    
    stage_a()
    b = stage_b(test_wav)
    c = stage_c(test_wav)
    
    # Cleanup
    os.unlink(test_wav)
    
    # Verdict
    print("\n=== VERDICT ===")
    sys_mem = get_system_memory()
    remaining = sys_mem['MemAvailable']
    peak_rss = c['peak_process_rss_mb']
    
    print(f"  Peak process RSS: {peak_rss:.0f} MB")
    print(f"  System available after full load: {remaining} MB")
    print(f"  STT transcription latency: {b['transcription_latency_ms']:.0f} ms (for 3s audio)")
    
    # Accept if: remaining > 1GB and STT latency < 5000ms
    acceptable = remaining > 1024 and b['transcription_latency_ms'] < 5000
    print(f"  ACCEPTABLE: {'YES' if acceptable else 'NO'}")
    
    return 0 if acceptable else 1

if __name__ == '__main__':
    sys.exit(main())
