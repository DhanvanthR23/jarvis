"""Sandbox filesystem isolation tests (G3).

Verifies that the sandbox correctly isolates the host filesystem.
These tests run actual bwrap commands.
"""

import os
import shutil
import tempfile
import unittest

from tests.sandbox.helpers import run_in_sandbox, REQUIRE_BWRAP


@REQUIRE_BWRAP
class TestFilesystemIsolation(unittest.TestCase):

    def test_cannot_read_host_ssh(self):
        """Sandbox must not be able to read ~/.ssh."""
        result = run_in_sandbox(['/usr/bin/ls', os.path.expanduser('~/.ssh')])
        self.assertNotEqual(result.returncode, 0)

    def test_cannot_read_host_home(self):
        """Sandbox must not see the real HOME directory."""
        real_home = os.path.expanduser('~')
        result = run_in_sandbox(['/usr/bin/ls', real_home])
        self.assertNotEqual(result.returncode, 0)

    def test_cannot_modify_host_etc(self):
        """Sandbox must not be able to write to /etc."""
        result = run_in_sandbox(
            ['/usr/bin/sh', '-c', 'echo test > /etc/jarvis_test_file'],
        )
        self.assertNotEqual(result.returncode, 0)

    def test_workspace_readable(self):
        """Workspace directory should be accessible inside sandbox."""
        with tempfile.TemporaryDirectory() as ws:
            # Create a test file in the workspace
            test_file = os.path.join(ws, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('hello')
            result = run_in_sandbox(
                ['/usr/bin/cat', '/home/agent/workspace/test.txt'],
                workspace_dir=ws,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), 'hello')

    def test_workspace_writable(self):
        """Should be able to create files in the workspace."""
        with tempfile.TemporaryDirectory() as ws:
            result = run_in_sandbox(
                ['/usr/bin/sh', '-c',
                 'echo created > /home/agent/workspace/new.txt && '
                 'cat /home/agent/workspace/new.txt'],
                workspace_dir=ws,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn('created', result.stdout)

    def test_tmp_is_private(self):
        """Sandbox should have its own /tmp, not the host's."""
        # Create a marker file in host /tmp
        marker = '/tmp/jarvis_sandbox_test_marker'
        try:
            with open(marker, 'w') as f:
                f.write('host')
            result = run_in_sandbox(
                ['/usr/bin/cat', '/tmp/jarvis_sandbox_test_marker'],
            )
            # Should fail because sandbox has its own /tmp
            self.assertNotEqual(result.returncode, 0)
        finally:
            if os.path.exists(marker):
                os.unlink(marker)


if __name__ == '__main__':
    unittest.main()
