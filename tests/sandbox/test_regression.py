"""Tests for automated sandbox regression (G4)."""

import unittest
from unittest.mock import patch, MagicMock
from jarvis.sandbox.regression import is_security_sensitive, run_security_suite


class TestRegression(unittest.TestCase):

    def test_is_security_sensitive_sandbox(self):
        self.assertTrue(is_security_sensitive('jarvis/sandbox/launcher.py'))

    def test_is_security_sensitive_policy(self):
        self.assertTrue(is_security_sensitive('jarvis/policy/engine.py'))

    def test_is_security_sensitive_mcp(self):
        self.assertTrue(is_security_sensitive('jarvis/mcp/server.py'))

    def test_is_security_sensitive_tools(self):
        self.assertTrue(is_security_sensitive('jarvis/tools/system.py'))

    def test_is_security_sensitive_capabilities(self):
        self.assertTrue(is_security_sensitive('capabilities.toml'))

    def test_is_security_sensitive_unrelated(self):
        self.assertFalse(is_security_sensitive('docs/readme.txt'))
        self.assertFalse(is_security_sensitive('jarvis/core/utils.py'))
        self.assertFalse(is_security_sensitive('jarvis/cli/main.py'))

    def test_run_security_suite_returns_bool(self):
        """Verify run_security_suite is callable and returns bool.

        We mock the actual test runner to avoid running the full
        sandbox suite recursively during test discovery.
        """
        with patch('jarvis.sandbox.regression.unittest.TextTestRunner') as mock_runner:
            mock_result = MagicMock()
            mock_result.wasSuccessful.return_value = True
            mock_runner.return_value.run.return_value = mock_result
            result = run_security_suite()
            self.assertIsInstance(result, bool)
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
