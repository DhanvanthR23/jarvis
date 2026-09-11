"""Tests for command execution tools."""
import unittest
from unittest.mock import MagicMock, patch

from jarvis.tools import commands


class TestCommands(unittest.TestCase):

    @patch('subprocess.run')
    def test_execute_allowlisted(self, mock_run):
        mock_run.return_value = MagicMock(stdout='hello', stderr='', returncode=0)
        res = commands.command_execute('ping', ['-c', '1', 'localhost'])
        self.assertEqual(res, 'hello')
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ['ping', '-c', '1', 'localhost'])

    def test_execute_not_allowlisted(self):
        res = commands.command_execute('rm', ['-rf', '/'])
        self.assertIn("not in the allowlist", res)

    def test_execute_systemctl_mutation_blocked(self):
        res = commands.command_execute('systemctl', ['restart', 'nginx'])
        self.assertIn("Use the service.restart tool", res)

    @patch('subprocess.run')
    def test_execute_systemctl_status_allowed(self, mock_run):
        mock_run.return_value = MagicMock(stdout='active', stderr='', returncode=0)
        res = commands.command_execute('systemctl', ['status', 'nginx'])
        self.assertEqual(res, 'active')
        
