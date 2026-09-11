"""Sandbox process isolation tests (G3).

Verifies PID namespace isolation.
"""

import unittest

import pytest

from tests.sandbox.helpers import REQUIRE_BWRAP, run_in_sandbox


@pytest.mark.integration
@REQUIRE_BWRAP
class TestProcessIsolation(unittest.TestCase):

    def test_pid_namespace_isolated(self):
        """Sandbox should have its own PID namespace with few visible PIDs."""
        result = run_in_sandbox([
            '/usr/bin/sh', '-c', 'ls -1 /proc | grep -cE "^[0-9]"',
        ])
        self.assertEqual(result.returncode, 0)
        pid_count = int(result.stdout.strip())
        # In an isolated PID namespace, should see very few processes
        self.assertLessEqual(pid_count, 10)

    def test_cannot_see_host_processes(self):
        """Sandbox should not see host process IDs like PID 1 (init/systemd)."""
        result = run_in_sandbox([
            '/usr/bin/sh', '-c', 'cat /proc/1/cmdline 2>/dev/null || echo DENIED',
        ])
        # Either the read fails or we see our own PID 1 (bwrap), not systemd
        if result.returncode == 0:
            # If we can read PID 1, it should NOT be systemd/init
            self.assertNotIn('systemd', result.stdout)
            self.assertNotIn('init', result.stdout)


if __name__ == '__main__':
    unittest.main()
