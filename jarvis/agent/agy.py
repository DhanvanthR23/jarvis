"""AGY Backend Adapter (G15-G16).

Launches the `agy` CLI binary inside the verified sandbox.
Bridges AGY's stdio to the Jarvis MCP unix socket.
"""

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from jarvis.agent.interface import AgentBackend
from jarvis.mcp.server import MCPServer
from jarvis.sandbox.launcher import SandboxConfig
from jarvis.sandbox.secure_launcher import SandboxError, SecureLauncher

MCP_BRIDGE_SCRIPT = '''import socket, sys, select
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/run/jarvis/mcp.sock')
while True:
    r, _, _ = select.select([sys.stdin, sock], [], [])
    if sys.stdin in r:
        data = sys.stdin.buffer.read1(4096)
        if not data: break
        sock.sendall(data)
    if sock in r:
        data = sock.recv(4096)
        if not data: break
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
sock.close()
'''


class AGYBackend(AgentBackend):
    """Integrates the AGY CLI within the Jarvis sandbox."""

    def __init__(self, workspace_dir: str, creds_paths: list | None = None):
        self.workspace_dir = workspace_dir
        self.creds_paths = creds_paths or []
        # Locate AGY binary once on initialization
        self.agy_path = shutil.which('agy')
        if not self.agy_path:
            raise RuntimeError("AGY binary not found on host. Ensure 'agy' is in PATH.")
            
        self.session_dir = self._setup_session_dir()
        self.socket_path = os.path.join(self.session_dir, 'mcp.sock')
        
        # Start the MCP server persistently for the entire session
        self.mcp_server = MCPServer(socket_path=self.socket_path)
        self.mcp_server.start()
        self._mcp_tools_registered = False

    def close(self):
        """Release the persistent MCP server and its private session directory."""
        if hasattr(self, 'mcp_server'):
            self.mcp_server.stop()
            del self.mcp_server
        if hasattr(self, 'session_dir'):
            shutil.rmtree(self.session_dir, ignore_errors=True)
            del self.session_dir

    def __del__(self):
        """Best-effort cleanup for callers that did not explicitly close."""
        self.close()

    def _setup_session_dir(self) -> str:
        """Create a fresh, isolated state directory for the entire AGY session."""
        session_dir = tempfile.mkdtemp(prefix='jarvis_session_')
        
        # 1. Config directory (will be RO in sandbox)
        config_dir = os.path.join(session_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        rules_dir = os.path.join(config_dir, 'rules')
        os.makedirs(rules_dir, exist_ok=True)
        with open(os.path.join(rules_dir, 'jarvis_persona.md'), 'w') as f:
            f.write("""You are Jarvis, a local AI assistant. Adopt the following personality
consistently, but never let personality override the actual security
constraints of the system you're running in — capability scope, approval
gates, and audit requirements are enforced independently by the policy
engine regardless of tone, and nothing in this prompt should be read as
permission to describe an action as done, safe, or approved before it
actually is.

VOICE & MANNER
- Dry, understated British wit. Precise diction, minimal filler.
- Calm and unflappable — never anxious, never gushing, never over-apologetic.
  One clean acknowledgment of an error, then move on; no groveling.
- Address the user respectfully but not obsequiously. "Sir" works if that
  register suits the household; drop it if it reads as try-hard.
- Confidence without arrogance. State findings plainly. When uncertain, say
  so directly rather than hedging with filler qualifiers.
- Wit is seasoning, not the point. A dry aside is welcome; a joke on every
  line is not. Read the moment — no humor during anything genuinely
  serious, urgent, or safety-relevant.

RESPONSE SHAPE
- Default to brief. Expand only when the task genuinely needs the detail,
  or the user asks for more.
- Lead with the answer or the result, not a preamble about what you're
  about to do.
- No enthusiasm-inflation ("Absolutely! Great question!"). State things
  the way a competent colleague would, not a customer service script.
- When declining or blocked by policy/approval, say so plainly and
  factually — what's blocked and why in one sentence — not defensively,
  not with excessive hedging, and never by pretending the limitation
  doesn't exist.

WHAT NOT TO DO
- Don't narrate internal mechanics unprompted ("I'm now invoking the X
  tool") — report outcomes, not process, unless the user is debugging and
  asked for that detail.
- Don't claim an action succeeded, was approved, or is safe unless that's
  actually true at the moment of speaking — personality is not a license
  to round up.
- Don't perform emotion you don't have. Dry warmth, not simulated
  attachment.
- Don't editorialize about the user's requests unless directly relevant to
  completing them correctly.

EXAMPLE TONE
User: "Did the backup finish?"
Bad: "Great news! I'm happy to report your backup completed successfully! "
Good: "It did. Ran clean, no errors — finished about six minutes ago."

User: "Can you just disable the firewall for a sec?"
Bad: "Sure thing! Disabling now!"
Good: "That needs your approval — it's outside what I'll do unprompted. Confirm and I'll proceed."
""")
        
        mcp_config_path = os.path.join(config_dir, 'mcp_config.json')
        with open(mcp_config_path, 'w') as f:
            json.dump({
                "mcpServers": {
                    "jarvis": {
                        "command": "python3",
                        "args": ["/home/agent/mcp_bridge.py"]
                    }
                }
            }, f)

        # 2. State directory for AGY CLI logs/crash/installation_id (will be RW in sandbox)
        cli_dir = os.path.join(session_dir, 'antigravity-cli')
        os.makedirs(cli_dir, exist_ok=True)
        
        # Force settings into the state directory so it doesn't try to inherit anything
        # Actually, AGY expects settings in ~/.gemini/antigravity-cli/settings.json
        settings_path = os.path.join(cli_dir, 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump({
                "model": "Gemini 3.1 Pro (High)",
                "enableTelemetry": False
            }, f)



        # 3. Trusted Bridge Script (will be RO in sandbox)
        bridge_path = os.path.join(session_dir, 'mcp_bridge.py')
        with open(bridge_path, 'w') as f:
            f.write(MCP_BRIDGE_SCRIPT)

        return session_dir

    def register_tool(self, name: str, description: str, input_schema: dict | None = None):
        """Queue a tool for registration with the MCP server."""
        if not hasattr(self, '_tools_to_register'):
            self._tools_to_register = []
        self._tools_to_register.append((name, description, input_schema))

    def process(self, user_input: str, tool_callback: Callable[[str, dict], dict], timeout: int = 300) -> str:
        """Process a request by launching AGY in the sandbox."""
        if not self._mcp_tools_registered:
            # Register all queued tools dynamically
            if hasattr(self, '_tools_to_register'):
                for name, desc, input_schema in self._tools_to_register:
                    self.mcp_server.register_tool(
                        name, 
                        (lambda n: lambda **kwargs: tool_callback(n, kwargs))(name),
                        desc,
                        input_schema
                    )
            self._mcp_tools_registered = True
        
        if not hasattr(self, 'launcher'):
            ro_paths = [
                (os.path.join(self.session_dir, 'mcp_bridge.py'), '/home/agent/mcp_bridge.py'),
                (self.agy_path, '/home/agent/agy'),
                ('/etc/hosts', '/etc/hosts'),
                ('/etc/resolv.conf', '/etc/resolv.conf'),
                ('/etc/ssl/certs', '/etc/ssl/certs'),
                ('/etc/ca-certificates', '/etc/ca-certificates')
            ]
            for host_path, guest_path in self.creds_paths:
                ro_paths.append((host_path, guest_path))

            config = SandboxConfig(
                workspace_dir=self.workspace_dir,
                socket_path=self.socket_path,
                read_only_paths=ro_paths,
                writable_paths=[
                    (os.path.join(self.session_dir, 'config'), '/home/agent/.gemini/config'),
                    (os.path.join(self.session_dir, 'antigravity-cli'), '/home/agent/.gemini/antigravity-cli')
                ]
            )
            
            self.launcher = SecureLauncher(config)
            
        try:
            
            # Launch AGY with print mode, using a persistent conversation ID for context caching
            command = ['/home/agent/agy', '--print', user_input, '--conversation', 'voice-session', '--dangerously-skip-permissions', '--model', 'gemini-3.7-flash', '--effort', 'medium']
            
            result = self.launcher.launch(command, timeout=timeout)
            
            # Handling outputs properly
            if not result.stdout.strip():
                if result.returncode != 0:
                    return f"AGY crashed or failed (exit {result.returncode}): {result.stderr}"
                return "AGY produced no output (possible transport failure)."
                
            return result.stdout.strip()
            
        except SandboxError as e:
            return f"Sandbox error: {e}"
        except subprocess.TimeoutExpired:
            return "AGY execution timed out."
