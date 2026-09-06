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
