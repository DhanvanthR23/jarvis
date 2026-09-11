"""CLI Entrypoint for Jarvis."""
import argparse
import sys

from jarvis.agent.mock import MockAgent  # Replace with real agent if needed? 
from jarvis.audit.logger import AuditLogger
from jarvis.core.controller import JarvisController
from jarvis.policy.approval import CLIApprovalHandler
from jarvis.policy.engine import PolicyEngine


def get_controller(backend_name: str = "mock") -> JarvisController:
    import os

    from jarvis.agent.agy import AGYBackend
    from jarvis.agent.mock import DEFAULT_SCENARIOS
    
    # Setup agent
    agent = None
    if backend_name == "agy":
        try:
            os.makedirs("/tmp/jarvis_workspace", exist_ok=True)
            creds_paths = []
            if "JARVIS_AGY_CREDS" in os.environ:
                if not os.environ["JARVIS_AGY_CREDS"].strip():
                    raise ValueError("JARVIS_AGY_CREDS is empty")
                for pair in os.environ["JARVIS_AGY_CREDS"].split(","):
                    if ":" not in pair:
                        raise ValueError(f"Malformed credential pair (missing colon): {pair}")
                    host, guest = pair.split(":", 1)
                    if not os.path.isabs(host):
                        raise ValueError(f"Host path must be absolute: {host}")
                    if not os.path.exists(host):
                        raise ValueError(f"Host credential path does not exist: {host}")
                    if not guest.startswith("/home/agent/.gemini/"):
                        raise ValueError(f"Guest path must be within /home/agent/.gemini/: {guest}")
                    creds_paths.append((host, guest))
            agent = AGYBackend(workspace_dir="/tmp/jarvis_workspace", creds_paths=creds_paths)
        except Exception as e:
            print(f"Warning: AGYBackend failed to initialize: {e}. Falling back to MockAgent.", file=sys.stderr)
            backend_name = "mock"
            
    if backend_name == "mock" or agent is None:
        agent = MockAgent(DEFAULT_SCENARIOS)

    # Setup Policy
    policy_engine = None
    manifest_path = "jarvis/policy/capabilities.toml"
    hash_path = "jarvis/policy/capabilities.hash"
    if os.path.exists(manifest_path) and os.path.exists(hash_path):
        from jarvis.policy.manifest import load_manifest
        with open(hash_path, 'r') as f:
            trusted_hash = f.read().strip()
        manifest = load_manifest(manifest_path, trusted_hash)
        policy_engine = PolicyEngine(manifest)
        
    approval_handler = CLIApprovalHandler()
    audit_logger = AuditLogger(db_path="/var/log/jarvis/audit.db", anchor_path="/var/log/jarvis/anchor.log")
    
    from jarvis.voice.session import VoiceSession
    voice_session = VoiceSession()

    controller = JarvisController(
        agent_backend=agent,
        policy_engine=policy_engine,
        approval_handler=approval_handler,
        audit_logger=audit_logger,
        voice_session=voice_session,
    )
    
    from jarvis.tools.registry import register_readonly_tools
    register_readonly_tools(controller)
    
    return controller

def main():
    parser = argparse.ArgumentParser(description="Jarvis CLI Entrypoint")
    parser.add_argument("query", nargs="*", help="Non-interactive query string")
    parser.add_argument("--voice", action="store_true", help="Launch Voice Runtime")
    parser.add_argument("--voice-engine", choices=["vosk", "faster-whisper"], default="vosk", help="Voice engine to use for STT/TTS (defaults to vosk)")
    parser.add_argument("--voice-name", default=None, help="Specific voice to use for Kokoro TTS (defaults to JARVIS_VOICE_NAME env var or am_michael)")
    parser.add_argument("--backend", choices=["mock", "agy"], help="Agent backend to use (defaults to 'mock' for one-shots, 'agy' for interactive REPL)")
    args = parser.parse_args()

    # Determine backend
    backend = args.backend
    if not backend:
        # Defaulting safely, but supporting live sandboxed AGY when running interactively or via voice
        if args.query:
            backend = "mock"
        else:
            backend = "agy"

    try:
        controller = get_controller(backend_name=backend)
    except Exception as e:
        print(f"Failed to initialize controller: {e}", file=sys.stderr)
        sys.exit(1)

    if args.voice:
        try:
            from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
            from jarvis.voice.runtime import VoiceRuntime
            from jarvis.voice.state import VoiceState
            from jarvis.voice.stt.local import VoskSTT
            from jarvis.voice.tts.local import PiperTTS

            # Try to load real PyAudio if installed
            try:
                from jarvis.voice.audio_real import PyAudioCapture, PyAudioPlayback
                capture = PyAudioCapture()
                playback = PyAudioPlayback()
                print("🎙️  Using real PyAudio for microphone and speakers")
            except ImportError:
                print("⚠️  PyAudio not installed (pip install PyAudio). Using Mock audio.", file=sys.stderr)
                capture = MockAudioCapture()
                playback = MockAudioPlayback()

            # Voice Engine Selection
            if getattr(args, 'voice_engine', 'vosk') == 'faster-whisper':
                from jarvis.voice.stt.faster_whisper import FasterWhisperSTT
                from jarvis.voice.tts.kokoro import (
                    KokoroTTS,
                    resolve_kokoro_voice_name,
                )
                
                resolved_voice_name = resolve_kokoro_voice_name(getattr(args, 'voice_name', None))
                
                stt = FasterWhisperSTT(model_size="base.en", compute_type="int8")
                tts = KokoroTTS(playback, voice_name=resolved_voice_name)
                
                if not stt.is_available() or not tts.is_available():
                    print("⚠️  Dependencies missing for faster-whisper/kokoro (pip install faster-whisper kokoro-onnx). Falling back to Vosk.", file=sys.stderr)
                    stt = VoskSTT(model_name="vosk-model-en-us-0.22-lgraph")
                    tts = PiperTTS(playback)
                else:
                    print(f"🚀 Using faster-whisper and Kokoro (Voice: {resolved_voice_name})")
            else:
                # Medium model (128MB) - excellent balance of speed and accuracy
                stt = VoskSTT(model_name="vosk-model-en-us-0.22-lgraph")
                tts = PiperTTS(playback)
            
            runtime = VoiceRuntime(capture=capture, playback=playback, stt=stt, tts=tts)
            
            # Connect the voice runtime to the controller
            def handle_transcription(transcript):
                if transcript.text:
                    print(f"\n🗣️  You said: {transcript.text}")
                    print("⚙️  Jarvis is thinking...")
                    response = controller.process_request(transcript.text, is_voice=True, transcript=transcript)
                    import re
                    clean_text = re.sub(r'[*_#`|~\[\]>]', '', response)
                    clean_text = re.sub(r'\n+', ' ', clean_text).strip()
                    print(f"🤖 Jarvis: {clean_text}")
                    runtime.speak(clean_text)
                else:
                    print("\n(No speech detected)")
                    runtime.state_machine.transition(VoiceState.IDLE)

            runtime.on_transcription = handle_transcription
            
            # Interactive voice loop
            while True:
                try:
                    runtime.start_listening()
                    action = input("\n🔴 Listening... (Press Enter to stop, or type 'q' to quit)\n")
                    if action.strip().lower() in ('q', 'quit', 'exit'):
                        print("\nGoodbye!")
                        # Ensure stream is stopped
                        if runtime.capture._recording:
                            runtime.capture.stop()
                        break
                    
                    print("🔄 Processing audio...")
                    runtime.stop_listening()
                except KeyboardInterrupt:
                    print("\n\nGoodbye!")
                    if runtime.capture._recording:
                        runtime.capture.stop()
                    break

        except ImportError as e:
            print(f"Voice support not available (missing dependencies: {e}).", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Voice runtime error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    query_text = " ".join(args.query).strip()

    if query_text:
        # One-shot mode
        try:
            response = controller.process_request(query_text)
            print(response)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # REPL mode
        print("Jarvis REPL active. Type 'exit' or 'quit' to quit.")
        while True:
            try:
                user_input = input("jarvis> ").strip()
                if user_input.lower() in ('exit', 'quit'):
                    break
                if not user_input:
                    continue
                
                response = controller.process_request(user_input)
                print(response)
            except KeyboardInterrupt:
                print("\nInterrupted by user. Type 'exit' to quit.")
            except EOFError:
                print()
                break
            except Exception as e:
                print(f"Runtime error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
