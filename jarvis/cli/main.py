"""CLI Entrypoint for Jarvis."""
import argparse
import sys

from jarvis.agent.mock import MockAgent  # Replace with real agent if needed? 
from jarvis.audit.logger import AuditLogger
from jarvis.core.controller import JarvisController
from jarvis.policy.approval import CLIApprovalHandler
from jarvis.policy.engine import PolicyEngine


def get_controller(backend_name: str = "mock", active_role: str = "system_diagnostics", verbose: bool = False) -> JarvisController:
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
        policy_engine = PolicyEngine(manifest, active_role=active_role)
        
    approval_handler = CLIApprovalHandler()
    if os.path.isdir("/var/log/jarvis") and os.access("/var/log/jarvis", os.W_OK):
        audit_db = "/var/log/jarvis/audit.db"
        audit_anchor = "/var/log/jarvis/anchor.log"
    else:
        audit_db = "audit.db"
        audit_anchor = "anchor.log"
        
    audit_logger = AuditLogger(db_path=audit_db, anchor_path=audit_anchor)
    
    from jarvis.voice.session import VoiceSession
    voice_session = VoiceSession()

    from jarvis.memory.store import MemoryStore, MemoryEntry, MemoryCategory
    from jarvis.memory.policy import MemoryPolicyEngine, MemoryWriteRequest
    import time
    
    memory_db_path = os.path.expanduser("~/.jarvis/memory.db")
    os.makedirs(os.path.dirname(memory_db_path), exist_ok=True)
    memory_store = MemoryStore(memory_db_path)
    memory_policy = MemoryPolicyEngine(memory_store, approval_handler=approval_handler)

    controller = JarvisController(
        agent_backend=agent,
        policy_engine=policy_engine,
        approval_handler=approval_handler,
        audit_logger=audit_logger,
        memory_store=memory_store,
        voice_session=voice_session,
        verbose=verbose,
    )
    
    from jarvis.tools.registry import register_readonly_tools
    register_readonly_tools(controller)
    
    # Register Memory Tools
    def memory_write(key: str, value: str, category: str = "facts"):
        try:
            cat = MemoryCategory(category)
        except ValueError:
            return {"status": "error", "message": f"Invalid category: {category}"}
            
        entry = MemoryEntry(
            key=key, value=value, category=cat, source="agent", 
            created_at=time.time(), updated_at=time.time(), confidence="agent_high_impact"
        )
        req = MemoryWriteRequest(entry=entry, source_type="agent_high_impact")
        success = memory_policy.process_write(req)
        return {"status": "success" if success else "denied"}

    def memory_read(key: str):
        entry = memory_store.read(key)
        if not entry:
            return {"status": "not_found"}
        return {"status": "success", "value": entry.value, "category": entry.category.value}

    def memory_search(query: str):
        results = memory_store.search(query=query)
        return {"status": "success", "results": [{"key": r.key, "value": r.value} for r in results]}

    controller.register_tool('memory_write', memory_write, 'Write a fact to persistent memory')
    controller.register_tool('memory_read', memory_read, 'Read a fact from persistent memory by key')
    controller.register_tool('memory_search', memory_search, 'Search persistent memory')

    return controller

def main():
    parser = argparse.ArgumentParser(description="Jarvis CLI Entrypoint")
    parser.add_argument("query", nargs="*", help="Non-interactive query string")
    parser.add_argument("--voice", action="store_true", help="Launch Voice Runtime")
    parser.add_argument("--stt-engine", choices=["whisper"], default="whisper", help="STT engine to use (defaults to whisper)")
    parser.add_argument("--tts-engine", choices=["piper", "cloud"], default="piper", help="TTS engine to use (defaults to piper)")
    parser.add_argument("--backend", choices=["mock", "agy"], help="Agent backend to use (defaults to 'mock' for one-shots, 'agy' for interactive REPL)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed logs about tool arguments, policy reasons, and outputs")
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
        controller = get_controller(backend_name=backend, active_role="system_diagnostics", verbose=args.verbose)
    except Exception as e:
        print(f"Failed to initialize controller: {e}", file=sys.stderr)
        sys.exit(1)

    if args.voice:
        try:
            from rich.console import Console
            from rich.panel import Panel
            console = Console()
            
            from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
            from jarvis.voice.runtime import VoiceRuntime
            from jarvis.voice.state import VoiceState
            from jarvis.voice.tts.local import PiperTTS

            # Try to load real PyAudio if installed
            try:
                from jarvis.voice.audio_real import PyAudioCapture, PyAudioPlayback
                capture = PyAudioCapture()
                playback = PyAudioPlayback()
                console.print("[green]  Using real PyAudio for microphone and speakers[/green]")
            except ImportError:
                console.print("[yellow]  PyAudio not installed (pip install PyAudio). Using Mock audio.[/yellow]")
                capture = MockAudioCapture()
                playback = MockAudioPlayback()

            # Engine Selection
            stt_engine = getattr(args, 'stt_engine', 'whisper')
            tts_engine = getattr(args, 'tts_engine', 'piper')

            # --- STT Setup ---
            if stt_engine == 'whisper':
                from jarvis.voice.stt.faster_whisper import FasterWhisperSTT
                model_size = "base.en"
                stt = FasterWhisperSTT(model_size=model_size, compute_type="int8")
                
                if not stt.is_available():
                    console.print("[red]  faster-whisper dependencies missing (pip install faster-whisper).[/red]")
                    sys.exit(1)
                else:
                    console.print(f"[cyan] Using Faster-Whisper STT (Model: {model_size})[/cyan]")

            # --- TTS Setup ---
            if tts_engine == 'cloud':
                from jarvis.voice.proxy.daemon import TTSProxyDaemon
                from jarvis.voice.tts.cloud import CloudTTS

                # Create Piper instance for daemon-side fallback
                piper_fallback = PiperTTS(playback)

                # Start the host-side proxy daemon
                tts_daemon = TTSProxyDaemon(
                    playback=playback,
                    piper_tts=piper_fallback,
                )
                tts_daemon.start()
                console.print(f"[cyan] TTS proxy daemon started on {tts_daemon.socket_path}[/cyan]")

                # Create the agent-side client (IPC-only, no network)
                tts = CloudTTS(playback, socket_path=tts_daemon.socket_path)

                if not tts.is_available():
                    console.print("[yellow]  Cloud TTS daemon not reachable. Falling back to Piper.[/yellow]")
                    tts_daemon.stop()
                    tts = piper_fallback
                else:
                    console.print("[cyan] Using Cloud TTS (Edge TTS via host-side proxy)[/cyan]")
            else:
                tts = PiperTTS(playback)
                console.print("[cyan] Using Piper TTS[/cyan]")
            
            runtime = VoiceRuntime(capture=capture, playback=playback, stt=stt, tts=tts)
            
            # Connect the voice runtime to the controller
            def handle_transcription(transcript):
                if transcript.text:
                    console.print(f"\n[bold blue]  You said:[/bold blue] {transcript.text}")
                    console.print("[dim]  Jarvis is thinking...[/dim]")
                    response = controller.process_request(transcript.text, is_voice=True, transcript=transcript)
                    import re
                    clean_text = re.sub(r'[*_#`|~\[\]>]', '', response)
                    clean_text = re.sub(r'\n+', ' ', clean_text).strip()
                    console.print(Panel(clean_text, title="󰚩 Jarvis", border_style="green"))
                    
                    import threading
                    import select
                    import sys
                    
                    speak_thread = threading.Thread(target=runtime.speak, args=(clean_text,))
                    speak_thread.start()
                    
                    console.print("[dim]󰚩 Jarvis is speaking... (Press Enter to interrupt)[/dim]")
                    
                    interrupted = False
                    while speak_thread.is_alive():
                        r, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if r:
                            sys.stdin.readline()
                            interrupted = True
                            break
                            
                    if interrupted:
                        runtime.interrupt()
                        console.print("[bold yellow]🛑 Interrupted![/bold yellow]")
                        # We do NOT join speak_thread here, so the UI can return instantly
                        # to listening. The thread will abort cleanly in the background
                        # due to the _stopped flag.
                        
                else:
                    console.print("\n[dim](No speech detected)[/dim]")
                    runtime.state_machine.transition(VoiceState.IDLE)

            runtime.on_transcription = handle_transcription
            
            # Interactive voice loop
            while True:
                try:
                    if runtime.state != VoiceState.LISTENING:
                        runtime.start_listening()
                    action = console.input("\n[bold red] Listening... (Press Enter to stop, or type 'q' to quit)[/bold red]\n")
                    if action.strip().lower() in ('q', 'quit', 'exit'):
                        console.print("\n[bold]Goodbye![/bold]")
                        # Ensure stream is stopped
                        if runtime.capture._recording:
                            runtime.capture.stop()
                        break
                    
                    console.print("[dim] Processing audio...[/dim]")
                    runtime.stop_listening()
                except KeyboardInterrupt:
                    console.print("\n\n[bold]Goodbye![/bold]")
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
        try:
            from rich.console import Console
            from rich.markdown import Markdown
            from rich.panel import Panel
            console = Console()
            ascii_art = r"""
     __       ____   ____  __    __  __  _____ 
    |  |     /    \ |    \|  |  |  ||  |/ ____|
    |  |    |  /\  ||  _  /|  |  |  ||  |   (   
 __ |  |    |  __  ||  |  \|  |__|  ||  |\___ \ 
|  \|  |    | |  | ||  |\  \\      / |  |____) |
 \____/     |_|  |_||__| \__\\____/  |__||_____/ 
            """
            console.print(Panel.fit(
                f"[bold cyan]{ascii_art}[/bold cyan]\n[green]Security-First AI Assistant[/green] • [bold]REPL Active[/bold]",
                border_style="cyan"
            ))
            console.print("[dim]Type 'exit' or 'quit' to quit.[/dim]\n")
            
            while True:
                try:
                    user_input = console.input("[bold cyan]jarvis[/bold cyan][bold white]>[/bold white] ").strip()
                    if user_input.lower() in ('exit', 'quit'):
                        break
                    if not user_input:
                        continue
                    
                    response = controller.process_request(user_input)
                    console.print("\n")
                    console.print(Markdown(response))
                    console.print("\n")
                except KeyboardInterrupt:
                    console.print("\n[yellow]Interrupted by user. Type 'exit' to quit.[/yellow]")
                except EOFError:
                    print()
                    break
                except Exception as e:
                    console.print(f"[bold red]Runtime error:[/bold red] {e}")

        except ImportError:
            # Fallback to standard REPL if rich is not available somehow
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
