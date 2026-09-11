"""Tests for read-only linux tools."""

import unittest
from unittest.mock import MagicMock, mock_open, patch

from jarvis.tools import files, logs, network, processes, system


class TestReadOnlyTools(unittest.TestCase):
    
    @patch('subprocess.run')
    def test_system_info(self, mock_run):
        mock_run.return_value = MagicMock(stdout='Linux mock_node 5.15.0\n', returncode=0)
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='PRETTY_NAME="Ubuntu 22.04"')):
                res = system.system_info()
                self.assertEqual(res['uname'], 'Linux mock_node 5.15.0')
                self.assertEqual(res['os_release']['PRETTY_NAME'], 'Ubuntu 22.04')

    @patch('subprocess.run')
    def test_network_interfaces(self, mock_run):
        mock_run.return_value = MagicMock(stdout='eth0: inet 10.0.0.2', returncode=0)
        self.assertEqual(network.network_interfaces(), 'eth0: inet 10.0.0.2')

    @patch('subprocess.run')
    def test_network_status(self, mock_run):
        mock_run.side_effect = [
            MagicMock(stdout='default via 10.0.0.1', returncode=0),
            MagicMock(stdout='tcp LISTEN 80', returncode=0),
        ]
        res = network.network_status()
        self.assertIn('default via 10.0.0.1', res)
        self.assertIn('tcp LISTEN 80', res)

    @patch('subprocess.run')
    def test_processes_list(self, mock_run):
        mock_run.return_value = MagicMock(stdout='PID 1 init', returncode=0)
        self.assertEqual(processes.processes_list(), 'PID 1 init')

    @patch('subprocess.run')
    def test_logs_search(self, mock_run):
        mock_run.return_value = MagicMock(stdout='log entry 1', returncode=0)
        res = logs.logs_search(service='ssh.service', grep='Failed')
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn('journalctl', cmd)
        self.assertIn('ssh.service', cmd)
        self.assertIn('Failed', cmd)
        self.assertEqual(res, 'log entry 1')

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isfile', return_value=True)
    def test_files_read(self, mock_isfile, mock_exists):
        with patch('builtins.open', mock_open(read_data='file content')):
            self.assertEqual(files.files_read('/path/to/file'), 'file content')

    @patch('os.path.exists', return_value=True)
    @patch('os.path.isdir', return_value=True)
    @patch('subprocess.run')
    def test_files_search(self, mock_run, mock_isdir, mock_exists):
        mock_run.return_value = MagicMock(stdout='/tmp/foo.txt', returncode=0)
        res = files.files_search('/tmp', '*.txt')
        self.assertEqual(res, '/tmp/foo.txt')
