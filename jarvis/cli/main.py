"""CLI Entrypoint for Jarvis."""
import argparse
import sys
from jarvis.core.controller import JarvisController
from jarvis.agent.mock import MockAgent  # Replace with real agent if needed? 
from jarvis.policy.engine import PolicyEngine
from jarvis.policy.manifest import load_manifest
from jarvis.policy.approval import CLIApprovalHandler
from jarvis.audit.logger import AuditLogger
from jarvis.audit.database import AuditDatabase


def get_controller(backend_name: str = "mock") -> JarvisController:
    import os
    from jarvis.agent.agy import AGYBackend
    from jarvis.agent.mock import MockAgent, DEFAULT_SCENARIOS
    
    # Setup agent
    agent = None
    if backend_name == "agy":
        try:
            os.makedirs("/tmp/jarvis_workspace", exist_ok=True)
            agent = AGYBackend(workspace_dir="/tmp/jarvis_workspace")
        except Exception as e:
            print(f"Warning: AGYBackend failed to initialize: {e}. Falling back to MockAgent.", file=sys.stderr)
            backend_name = "mock"
            
    if backend_name == "mock" or agent is None:
        agent = MockAgent(DEFAULT_SCENARIOS)

    # Setup Policy
    policy_engine = None
    manifest_path = "jarvis/policy/capabilities.toml"
    if os.path.exists(manifest_path):
        from jarvis.policy.manifest import CapabilityManifest
        manifest = CapabilityManifest(manifest_path)
        manifest.load()
        policy_engine = PolicyEngine(manifest)
        
    approval_handler = CLIApprovalHandler()

    return JarvisController(
        agent_backend=agent,
        policy_engine=policy_engine,
        approval_handler=approval_handler,
    )

def main():
    parser = argparse.ArgumentParser(description="Jarvis CLI Entrypoint")
    parser.add_argument("query", nargs="*", help="Non-interactive query string")
    parser.add_argument("--voice", action="store_true", help="Launch Voice Runtime")
    parser.add_argument("--backend", choices=["mock", "agy"], help="Agent backend to use (defaults to 'mock' for one-shots, 'agy' for interactive REPL)")
    args = parser.parse_args()

    # Determine backend
    backend = args.backend
    if not backend:
        # Defaulting safely, but supporting live sandboxed AGY when running interactively
        if args.query or args.voice:
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
            from jarvis.voice.runtime import VoiceRuntime
            runtime = VoiceRuntime(controller=controller)
            runtime.start()
        except ImportError:
            print("Voice support not available.", file=sys.stderr)
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
