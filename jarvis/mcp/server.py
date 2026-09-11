import json
import os
import socket
import threading
from collections.abc import Callable


class MCPServer:
    def __init__(self, socket_path: str, tool_registry: dict[str, Callable] | None = None, policy_engine=None, audit_logger=None):
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
        
        if method == "initialize":
            return {
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "jarvis",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "notifications/initialized":
            return None # Notifications don't need a response
        elif method == "tools/list":
            return {"result": {"tools": [{"name": k, "description": v["description"], "inputSchema": {"type": "object", "properties": {}}} for k, v in self.tool_registry.items()]}}
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {}) # Note: MCP uses 'arguments', not 'args'
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
                    return {"error": {"code": -32001, "message": "Approval required"}}
            
            try:
                result = self.tool_registry[tool_name]["handler"](**args)
                if self.audit_logger:
                    self.audit_logger.log_event("session_0", "agent", tool_name, args, policy_decision, approval_decision, str(result)[:100])
                
                # Format output properly for MCP
                content = [{"type": "text", "text": str(result)}]
                return {"result": {"content": content}}
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
                except TimeoutError:
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
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        request_dict = json.loads(line.decode("utf-8"))
                        response_dict = self._handle_request(request_dict)
                        if response_dict is not None:
                            response_dict["id"] = request_dict.get("id", "")
                            response_dict["jsonrpc"] = "2.0"
                            conn.sendall((json.dumps(response_dict) + "\n").encode("utf-8"))
                except Exception:
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

    def call(self, method: str, params: dict | None = None) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        req = {"method": method, "params": params or {}, "id": "1"}
        sock.sendall((json.dumps(req) + "\n").encode("utf-8"))
        
        buffer = b""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
            if b"\n" in buffer:
                line, _ = buffer.split(b"\n", 1)
                return json.loads(line.decode("utf-8"))
        return {}

    def list_tools(self) -> list:
        res = self.call("tools/list")
        return res.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        return self.call("tools/call", {"name": tool_name, "arguments": arguments or {}})
