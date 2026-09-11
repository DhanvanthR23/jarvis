"""Tests for sandbox preflight checks (G1)."""

import unittest
from unittest.mock import patch

from jarvis.sandbox.preflight import CheckResult, PreflightResult, run_preflight


class TestPreflight(unittest.TestCase):

    def test_run_preflight_returns_result(self):
        result = run_preflight()
        self.assertIsInstance(result, PreflightResult)
        self.assertIsInstance(result.passed, bool)
        self.assertIsInstance(result.checks, dict)

    def test_expected_check_names(self):
        result = run_preflight()
        expected = {
            'bwrap_available', 'user_namespace', 'pid_namespace',
            'network_namespace', 'full_isolation', 'unix_socket',
        }
        self.assertEqual(set(result.checks.keys()), expected)

    def test_check_result_fields(self):
        result = run_preflight()
        for check in result.checks.values():
            self.assertIsInstance(check, CheckResult)
            self.assertIsInstance(check.name, str)
            self.assertIsInstance(check.passed, bool)
            self.assertIsInstance(check.detail, str)
            self.assertTrue(len(check.detail) > 0)

    def test_bwrap_available_passes(self):
        """On a system with bwrap installed, this check should pass."""
        import shutil
        result = run_preflight()
        if shutil.which('bwrap'):
            self.assertTrue(result.checks['bwrap_available'].passed)

    def test_failure_makes_overall_fail(self):
        """If any individual check fails, overall result is FAIL."""
        with patch('jarvis.sandbox.preflight.shutil.which', return_value=None):
            result = run_preflight()
            self.assertFalse(result.passed)


if __name__ == '__main__':
    unittest.main()
