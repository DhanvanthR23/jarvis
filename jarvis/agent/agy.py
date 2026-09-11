"""AGY Backend Adapter (G15-G16).

Launches the `agy` CLI binary inside the verified sandbox.
Bridges AGY's stdio to the Jarvis MCP unix socket.
"""

import json
import os
import shutil
import subprocess
import tempfile
from typing import Callable

from jarvis.agent.interface import AgentBackend
from jarvis.sandbox.launcher import SandboxConfig
from jarvis.sandbox.secure_launcher import SecureLauncher, SandboxError
from jarvis.mcp.server import MCPServer

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

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        # Locate AGY binary once on initialization
        self.agy_path = shutil.which('agy')
        if not self.agy_path:
            raise RuntimeError("AGY binary not found on host. Ensure 'agy' is in PATH.")

    def _setup_session_dir(self) -> str:
        """Create a fresh, isolated state directory for a single AGY invocation."""
        session_dir = tempfile.mkdtemp(prefix='jarvis_session_')
        
        # 1. Config directory (will be RO in sandbox)
        config_dir = os.path.join(session_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        
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

        # Also copy antigravity-oauth-token to the cli_dir so it can authenticate
        src_token = os.path.expanduser('~/.gemini/antigravity-cli/antigravity-oauth-token')
        if os.path.exists(src_token):
            shutil.copy(src_token, os.path.join(cli_dir, 'antigravity-oauth-token'))

        # 3. Trusted Bridge Script (will be RO in sandbox)
        bridge_path = os.path.join(session_dir, 'mcp_bridge.py')
        with open(bridge_path, 'w') as f:
            f.write(MCP_BRIDGE_SCRIPT)

        return session_dir

    def process(self, user_input: str, tool_callback: Callable[[str, dict], dict]) -> str:
        """Process a request by launching AGY in the sandbox."""
        session_dir = self._setup_session_dir()
        socket_path = os.path.join(session_dir, 'mcp.sock')
        
        # Start the MCP server on the host, listening on the socket
        mcp_server = MCPServer(socket_path=socket_path)
        
        # For G15 testing, map a mock tool. We will expand this in G17.
        mcp_server.register_tool(
            'system_info', 
            lambda **kwargs: tool_callback('system_info', kwargs), 
            'Get system info'
        )
        
        mcp_server.start()
        
        try:
            config = SandboxConfig(
                workspace_dir=self.workspace_dir,
                socket_path=socket_path,
                read_only_paths=[
                    (os.path.join(session_dir, 'mcp_bridge.py'), '/home/agent/mcp_bridge.py'),
                    (self.agy_path, '/home/agent/agy'),
                    ('/etc/hosts', '/etc/hosts'),
                    ('/etc/resolv.conf', '/etc/resolv.conf'),
                    ('/etc/ssl/certs', '/etc/ssl/certs'),
                    ('/etc/ca-certificates', '/etc/ca-certificates'),
                    ('/home/dhanvanth/.gemini/oauth_creds.json', '/home/agent/.gemini/oauth_creds.json'),
                    ('/home/dhanvanth/.gemini/google_accounts.json', '/home/agent/.gemini/google_accounts.json')
                ],
                writable_paths=[
                    (os.path.join(session_dir, 'config'), '/home/agent/.gemini/config'),
                    (os.path.join(session_dir, 'antigravity-cli'), '/home/agent/.gemini/antigravity-cli')
                ]
            )
            
            launcher = SecureLauncher(config)
            
            # Launch AGY with print mode
            command = ['/home/agent/agy', '--print', user_input, '--dangerously-skip-permissions', '--model', 'gemini-3.7-flash', '--effort', 'medium']
            
            try:
                result = launcher.launch(command, timeout=300)
                
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
                
        finally:
            mcp_server.stop()
            # Absolute cleanup of the session directory
            # shutil.rmtree(session_dir, ignore_errors=True)
            print(f"DEBUG: session_dir kept at {session_dir}")
