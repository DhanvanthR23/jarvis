import os

files = {}

files['/home/dhanvanth/projects/jarvis/jarvis/mcp/__init__.py'] = '''\
'''

files['/home/dhanvanth/projects/jarvis/jarvis/mcp/protocol.py'] = '''\
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class MCPRequest:
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class MCPResponse:
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

def serialize_request(request: MCPRequest) -> bytes:
    data = {"method": request.method, "params": request.params, "id": request.id}
    return (json.dumps(data) + "\\n").encode("utf-8")

def deserialize_request(data: bytes) -> MCPRequest:
    parsed = json.loads(data.decode("utf-8").strip())
    return MCPRequest(method=parsed["method"], params=parsed.get("params", {}), id=parsed.get("id", str(uuid.uuid4())))

def serialize_response(response: MCPResponse) -> bytes:
    data = {"id": response.id, "result": response.result, "error": response.error}
    return (json.dumps(data) + "\\n").encode("utf-8")

def deserialize_response(data: bytes) -> MCPResponse:
    parsed = json.loads(data.decode("utf-8").strip())
    return MCPResponse(id=parsed["id"], result=parsed.get("result"), error=parsed.get("error"))
'''

files['/home/dhanvanth/projects/jarvis/jarvis/mcp/server.py'] = '''\
import os
import socket
import threading
import json
from typing import Callable, Dict, Any
from .protocol import deserialize_request, serialize_response, MCPResponse

class MCPServer:
    def __init__(self, socket_path: str, tool_registry: Dict[str, Callable] = None, policy_engine=None, audit_logger=None):
        if not os.path.isabs(socket_path):
            raise ValueError("socket_path must be an absolute path")
        self.socket_path = socket_path
        self.tool_registry = tool_registry or {}
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger
        self.running = False
        self.sock = None
        self._ensure_socket_dir()

    def _ensure_socket_dir(self):
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)

    def register_tool(self, name: str, handler: Callable, description: str = ''):
        self.tool_registry[name] = {"handler": handler, "description": description}

    def _handle_request(self, request: dict) -> dict:
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "tools/list":
            return {"result": {"tools": [{"name": k, "description": v["description"]} for k, v in self.tool_registry.items()]}}
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("args", {})
            if tool_name not in self.tool_registry:
                return {"error": {"code": -32601, "message": "Unknown tool"}}
            
            # Policy Engine Check
            policy_decision = "ALLOW"
            approval_decision = None
            if self.policy_engine:
                decision_result = self.policy_engine.check(tool_name, args)
                policy_decision = decision_result.decision.name
                if policy_decision == "DENY":
                    return {"error": {"code": -32000, "message": f"Policy denied: {decision_result.reason}"}}
                elif policy_decision == "APPROVE":
                    # For MVP, if no approval_handler is invoked here, we just assume DENY if not explicitly handled
                    # Or handled by policy_engine internally. Let's assume APPROVE means we need approval but it's not handled here
                    return {"error": {"code": -32001, "message": "Approval required"}}
            
            try:
                result = self.tool_registry[tool_name]["handler"](**args)
                if self.audit_logger:
                    self.audit_logger.log_event("session_0", "agent", tool_name, args, policy_decision, approval_decision, str(result)[:100])
                return {"result": result}
            except Exception as e:
                return {"error": {"code": -32603, "message": str(e)}}
        else:
            return {"error": {"code": -32601, "message": "Method not found"}}

    def start(self):
        self._ensure_socket_dir()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.socket_path)
        self.sock.listen(5)
        self.running = True
        
        def accept_loop():
            while self.running:
                try:
                    self.sock.settimeout(1.0)
                    conn, _ = self.sock.accept()
                    threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception:
                    if self.running:
                        pass
        
        self._server_thread = threading.Thread(target=accept_loop, daemon=True)
        self._server_thread.start()

    def _handle_client(self, conn):
        with conn:
            buffer = b""
            while self.running:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buffer += data
                    if b"\\n" in buffer:
                        line, buffer = buffer.split(b"\\n", 1)
                        request_dict = json.loads(line.decode("utf-8"))
                        response_dict = self._handle_request(request_dict)
                        response_dict["id"] = request_dict.get("id", "")
                        conn.sendall((json.dumps(response_dict) + "\\n").encode("utf-8"))
                except Exception as e:
                    break

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

class MCPClient:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def call(self, method: str, params: dict = None) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        req = {"method": method, "params": params or {}, "id": "1"}
        sock.sendall((json.dumps(req) + "\\n").encode("utf-8"))
        
        buffer = b""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
            if b"\\n" in buffer:
                line, _ = buffer.split(b"\\n", 1)
                return json.loads(line.decode("utf-8"))
        return {}

    def list_tools(self) -> list:
        res = self.call("tools/list")
        return res.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, args: dict = None) -> dict:
        return self.call("tools/call", {"name": tool_name, "args": args or {}})
'''

files['/home/dhanvanth/projects/jarvis/tests/mcp/__init__.py'] = ''

files['/home/dhanvanth/projects/jarvis/tests/mcp/test_server.py'] = '''\
import os
import time
import tempfile
import unittest
from jarvis.mcp.server import MCPServer, MCPClient

class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.sock_fd, self.sock_path = tempfile.mkstemp()
        os.close(self.sock_fd)
        os.remove(self.sock_path)
        self.server = MCPServer(self.sock_path)
        
    def tearDown(self):
        self.server.stop()
        
    def test_register_and_list_tools(self):
        self.server.register_tool("echo", lambda x: x, "Echo tool")
        res = self.server._handle_request({"method": "tools/list", "id": "1"})
        self.assertEqual(res["result"]["tools"][0]["name"], "echo")
        
    def test_call_tool(self):
        self.server.register_tool("add", lambda a, b: a + b)
        res = self.server._handle_request({"method": "tools/call", "params": {"name": "add", "args": {"a": 2, "b": 3}}, "id": "1"})
        self.assertEqual(res["result"], 5)
        
    def test_unknown_tool(self):
        res = self.server._handle_request({"method": "tools/call", "params": {"name": "not_exist", "args": {}}, "id": "1"})
        self.assertIn("error", res)
        
    def test_client_server_integration(self):
        self.server.register_tool("hello", lambda name: f"Hello {name}")
        self.server.start()
        time.sleep(0.1)
        client = MCPClient(self.sock_path)
        tools = client.list_tools()
        self.assertEqual(tools[0]["name"], "hello")
        res = client.call_tool("hello", {"name": "World"})
        self.assertEqual(res["result"], "Hello World")
'''

for path, content in files.items():
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)

