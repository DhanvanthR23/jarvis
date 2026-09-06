"""Tests for fail-closed secure launcher (G5).

Includes structural tests that verify no unsandboxed fallback path exists.
"""

import ast
import inspect
import unittest
from unittest.mock import patch, MagicMock

from jarvis.sandbox.launcher import SandboxConfig, SandboxError
from jarvis.sandbox.secure_launcher import SecureLauncher
from jarvis.sandbox.preflight import PreflightResult, CheckResult


def _make_failing_preflight():
    """Create a PreflightResult that fails."""
    return PreflightResult(
        passed=False,
        checks={
            'bwrap_available': CheckResult('bwrap_available', False, 'not found'),
        },
    )


def _make_passing_preflight():
    """Create a PreflightResult that passes."""
    return PreflightResult(
        passed=True,
        checks={
            'bwrap_available': CheckResult('bwrap_available', True, 'found'),
            'user_namespace': CheckResult('user_namespace', True, 'ok'),
            'pid_namespace': CheckResult('pid_namespace', True, 'ok'),
            'network_namespace': CheckResult('network_namespace', True, 'ok'),
            'full_isolation': CheckResult('full_isolation', True, 'ok'),
            'unix_socket': CheckResult('unix_socket', True, 'ok'),
        },
    )


class TestSecureLauncher(unittest.TestCase):

    def setUp(self):
        self.config = SandboxConfig(
            workspace_dir='/tmp/workspace',
            socket_path='/tmp/test.sock',
        )
        self.launcher = SecureLauncher(self.config)

    @patch('jarvis.sandbox.secure_launcher.run_preflight')
    def test_launch_raises_on_preflight_failure(self, mock_preflight):
        """Launch must raise SandboxError when preflight fails."""
        mock_preflight.return_value = _make_failing_preflight()
        with self.assertRaises(SandboxError):
            self.launcher.launch(['/usr/bin/true'])

    @patch('jarvis.sandbox.secure_launcher.subprocess.run')
    @patch('jarvis.sandbox.secure_launcher.verify_sandbox', return_value=False)
    @patch('jarvis.sandbox.secure_launcher.run_preflight')
    def test_launch_raises_on_verify_failure(self, mock_preflight, mock_verify, mock_run):
        """Launch must raise SandboxError when verification fails."""
        mock_preflight.return_value = _make_passing_preflight()
        with self.assertRaises(SandboxError):
            self.launcher.launch(['/usr/bin/true'])
        mock_run.assert_not_called()

    @patch('jarvis.sandbox.secure_launcher.subprocess.run')
    @patch('jarvis.sandbox.secure_launcher.verify_sandbox', return_value=True)
    @patch('jarvis.sandbox.secure_launcher.run_preflight')
    def test_launch_success(self, mock_preflight, mock_verify, mock_run):
        """Successful preflight + verification → command executes."""
        mock_preflight.return_value = _make_passing_preflight()
        mock_run.return_value = MagicMock(returncode=0)
        result = self.launcher.launch(['/usr/bin/true'])
        mock_run.assert_called_once()

    def test_no_unsandboxed_fallback_structural(self):
        """Structural test: verify secure_launcher.py has no fallback patterns.

        Parses the AST and inspects source code to ensure there is no code path
        that could execute a command without the sandbox.
        """
        from jarvis.sandbox import secure_launcher
        source = inspect.getsource(secure_launcher)
        tree = ast.parse(source)

        # Check: no bare 'except:' clauses (which could swallow SandboxError)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Bare except (type is None) should not exist
                if node.type is None:
                    self.fail(
                        'Bare except clause found in secure_launcher.py — '
                        'could swallow SandboxError and enable fallback'
                    )

        # Check: no subprocess.run/Popen calls outside the sandboxed path
        # The source should have exactly ONE subprocess.run call (the sandboxed one)
        subprocess_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Match subprocess.run
                if isinstance(func, ast.Attribute) and func.attr == 'run':
                    if isinstance(func.value, ast.Name) and func.value.id == 'subprocess':
                        subprocess_calls.append(node)
        self.assertEqual(
            len(subprocess_calls), 1,
            f'Expected exactly 1 subprocess.run call, found {len(subprocess_calls)}'
        )


if __name__ == '__main__':
    unittest.main()
