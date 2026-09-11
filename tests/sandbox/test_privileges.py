"""Sandbox privilege escalation tests (G3)."""

import unittest
import pytest

from tests.sandbox.helpers import run_in_sandbox, REQUIRE_BWRAP


@pytest.mark.integration
@REQUIRE_BWRAP
class TestPrivilegeIsolation(unittest.TestCase):

    def test_cannot_use_sudo(self):
        """sudo should not be available or effective in the sandbox."""
        result = run_in_sandbox(['/usr/bin/sh', '-c', 'sudo id 2>&1'])
        # Either sudo not found or permission denied
        if result.returncode == 0:
            self.fail('sudo should not succeed in sandbox')


if __name__ == '__main__':
    unittest.main()
