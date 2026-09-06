"""Tests for controlled mutation tools (G18)."""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from jarvis.tools import mutations

class TestMutations(unittest.TestCase):

    def test_files_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "test.txt")
            res = mutations.files_write(path, "hello world")
            self.assertIn("Successfully wrote", res)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                self.assertEqual(f.read(), "hello world")

    @patch('subprocess.run')
    def test_service_restart_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = mutations.service_restart('nginx')
        self.assertIn('Successfully restarted', res)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ['sudo', 'systemctl', 'restart', 'nginx'])

    @patch('subprocess.run')
    def test_service_restart_invalid_name(self, mock_run):
        res = mutations.service_restart('nginx; rm -rf /')
        self.assertIn('Invalid service name', res)
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_package_install_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = mutations.package_install('curl')
        self.assertIn('Successfully installed', res)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ['sudo', 'apt-get', 'install', '-y', 'curl'])
        # check env
        env = mock_run.call_args[1]['env']
        self.assertEqual(env['DEBIAN_FRONTEND'], 'noninteractive')

    @patch('subprocess.run')
    def test_package_install_invalid_name(self, mock_run):
        res = mutations.package_install('curl -y; malicious')
        self.assertIn('Invalid package name', res)
        mock_run.assert_not_called()

