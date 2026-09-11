import tempfile
"""Tests for AGYBackend adapter (G15/G16)."""

import os
import shutil
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from jarvis.agent.agy import AGYBackend
from jarvis.sandbox.launcher import SandboxError


class TestAGYBackend(unittest.TestCase):

    def setUp(self):
        self.workspace = '/tmp/jarvis_test_ws_agy'
        os.makedirs(self.workspace, exist_ok=True)
        # Mock shutil.which so it doesn't fail if agy is missing in the test environment
        with patch('jarvis.agent.agy.shutil.which', return_value='/fake/bin/agy'):
            self.backend = AGYBackend(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_session_directory_cleanup_on_success(self):
        """Regression assertion: no session-state directory remains after normal execution."""
        
        # Track the created directory
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp
        
        def mock_mkdtemp(*args, **kwargs):
            d = original_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d
            
        with patch('jarvis.agent.agy.tempfile.mkdtemp', side_effect=mock_mkdtemp):
            with patch('jarvis.agent.agy.SecureLauncher.launch') as mock_launch:
                mock_launch.return_value = MagicMock(stdout='Hello', returncode=0)
                
                result = self.backend.process('hi', lambda n, a: {})
                self.assertEqual(result, 'Hello')
                
        self.assertEqual(len(created_dirs), 1)
        self.assertFalse(os.path.exists(created_dirs[0]), "Session directory was not cleaned up!")

    def test_session_directory_cleanup_on_error(self):
        """Regression assertion: no session-state directory remains after crash/error."""
        
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp
        
        def mock_mkdtemp(*args, **kwargs):
            d = original_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d
            
        with patch('jarvis.agent.agy.tempfile.mkdtemp', side_effect=mock_mkdtemp):
            with patch('jarvis.agent.agy.SecureLauncher.launch', side_effect=SandboxError("Launch failed")):
                result = self.backend.process('hi', lambda n, a: {})
                self.assertTrue(result.startswith("Sandbox error:"))
                
        self.assertEqual(len(created_dirs), 1)
        self.assertFalse(os.path.exists(created_dirs[0]), "Session directory was not cleaned up on error!")

    def test_sandbox_mounts_correctly(self):
        """Verify the exact RO/RW filesystem assumptions for AGY."""
        
        with patch('jarvis.agent.agy.SecureLauncher') as mock_launcher_class:
            mock_instance = mock_launcher_class.return_value
            mock_instance.launch.return_value = MagicMock(stdout='Done', returncode=0)
            
            self.backend.process('test', lambda n, a: {})
            
            # Extract the SandboxConfig that was passed to SecureLauncher
            config = mock_launcher_class.call_args[0][0]
            
            # Verify read_only_paths
            ro_dests = [dest for _, dest in config.read_only_paths]
            self.assertIn('/home/agent/mcp_bridge.py', ro_dests)
            self.assertIn('/home/agent/agy', ro_dests)
            
            # Verify writable_paths
            rw_dests = [dest for _, dest in config.writable_paths]
            self.assertIn('/home/agent/.gemini/config', rw_dests)
            self.assertIn('/home/agent/.gemini/antigravity-cli', rw_dests)
            
            # Verify no host home directory is hardcoded in the source tree (except via config)
            # The test doesn't supply creds_paths, so we shouldn't see /home/ sources
            for path_tuple in config.read_only_paths + config.writable_paths:
                src, _ = path_tuple
                if path_tuple not in self.backend.creds_paths:
                    self.assertNotIn('/home/dhanvanth', src) # Host home is not hardcoded

    def test_empty_output_handling(self):
        """Empty output from AGY is treated as transport failure."""
        with patch('jarvis.agent.agy.SecureLauncher.launch') as mock_launch:
            mock_launch.return_value = MagicMock(stdout='', stderr='', returncode=0)
            result = self.backend.process('hi', lambda n, a: {})
            self.assertIn('AGY produced no output', result)
            
    def test_crash_handling(self):
        """Non-zero exit code with empty stdout reports the error."""
        with patch('jarvis.agent.agy.SecureLauncher.launch') as mock_launch:
            mock_launch.return_value = MagicMock(stdout='', stderr='Segfault', returncode=139)
            result = self.backend.process('hi', lambda n, a: {})
            self.assertIn('AGY crashed or failed (exit 139)', result)
            self.assertIn('Segfault', result)

    def test_timeout_handling(self):
        """Timeouts are caught and reported cleanly."""
        with patch('jarvis.agent.agy.SecureLauncher.launch', side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60)):
            result = self.backend.process('hi', lambda n, a: {})
            self.assertEqual(result, 'AGY execution timed out.')



if __name__ == '__main__':
    unittest.main()
