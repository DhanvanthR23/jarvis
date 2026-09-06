import os
from jarvis.agent.agy import AGYBackend
from jarvis.core.controller import JarvisController
from jarvis.sandbox.preflight import run_preflight

def main():
    if not run_preflight().passed:
        print("Preflight failed. Cannot run sandbox.")
        return

    workspace = os.path.abspath('/tmp/jarvis_test_ws')
    os.makedirs(workspace, exist_ok=True)

    backend = AGYBackend(workspace_dir=workspace)
    controller = JarvisController(agent_backend=backend)
    
    # Register our dummy tool so JarvisController can handle it
    controller.register_tool('system.info', lambda: {"os": "JarvisOS"}, "Get system info")

    print("Sending prompt to AGY...")
    response = controller.process_request("Use the system.info tool to check the OS, then reply with just the OS name.")
    
    print("\n--- AGY Response ---")
    print(response)
    print("--------------------")

if __name__ == '__main__':
    main()
