"""Sandbox network isolation tests (G3).

Verifies that the sandbox has controlled network access required for AGY. and that the MCP socket is accessible.
"""

import unittest
import pytest

from tests.sandbox.helpers import run_in_sandbox, REQUIRE_BWRAP


@pytest.mark.integration
@REQUIRE_BWRAP
class TestNetworkIsolation(unittest.TestCase):

    def test_has_network_access(self):
        """Sandbox must have network access for AGY."""
        # Try to create a TCP socket — should succeed because we use --share-net
        result = run_in_sandbox([
            '/usr/bin/python3', '-c',
            'import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); '
            's.settimeout(1); s.connect(("8.8.8.8", 53))',
        ])
        self.assertEqual(result.returncode, 0)

    def test_mcp_socket_path_exists(self):
        """The MCP socket path should exist inside the sandbox."""
        result = run_in_sandbox([
            '/usr/bin/test', '-e', '/run/jarvis/mcp.sock',
        ])
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
