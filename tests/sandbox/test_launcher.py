"""Tests for sandbox launcher (G2)."""

import os
import unittest
from jarvis.sandbox.launcher import (
    SandboxConfig, SandboxError, DEFAULT_ENV, FORBIDDEN_ENV_VARS,
    build_bwrap_command, is_forbidden_env,
)


class TestBuildBwrapCommand(unittest.TestCase):

    def setUp(self):
        self.config = SandboxConfig(
            workspace_dir='/tmp/test_workspace',
            socket_path='/tmp/test.sock',
        )
        self.cmd = build_bwrap_command(self.config, ['/usr/bin/echo', 'hello'])

    def test_starts_with_bwrap(self):
        self.assertEqual(self.cmd[0], 'bwrap')

    def test_unshare_all_present(self):
        self.assertIn('--unshare-all', self.cmd)

    def test_die_with_parent(self):
        self.assertIn('--die-with-parent', self.cmd)

    def test_clearenv_present(self):
        self.assertIn('--clearenv', self.cmd)

    def test_default_env_set(self):
        for key, value in DEFAULT_ENV.items():
            idx = self.cmd.index('--setenv')
            # Find the specific setenv for this key
            found = False
            for i, arg in enumerate(self.cmd):
                if arg == '--setenv' and i + 1 < len(self.cmd) and self.cmd[i + 1] == key:
                    self.assertEqual(self.cmd[i + 2], value)
                    found = True
                    break
            self.assertTrue(found, f'--setenv {key} not found in command')

    def test_workspace_bind_mount(self):
        # Find --bind workspace_dir /home/agent/workspace
        for i, arg in enumerate(self.cmd):
            if arg == '--bind' and i + 2 < len(self.cmd):
                if self.cmd[i + 1] == '/tmp/test_workspace':
                    self.assertEqual(self.cmd[i + 2], '/home/agent/workspace')
                    return
        self.fail('Workspace bind mount not found')

    def test_socket_bind_mount(self):
        # Find --ro-bind socket_path /run/jarvis/mcp.sock
        for i, arg in enumerate(self.cmd):
            if arg == '--ro-bind' and i + 2 < len(self.cmd):
                if self.cmd[i + 1] == '/tmp/test.sock':
                    self.assertEqual(self.cmd[i + 2], '/run/jarvis/mcp.sock')
                    return
        self.fail('Socket bind mount not found')

    def test_usr_readonly(self):
        for i, arg in enumerate(self.cmd):
            if arg == '--ro-bind' and i + 2 < len(self.cmd):
                if self.cmd[i + 1] == '/usr' and self.cmd[i + 2] == '/usr':
                    return
        self.fail('/usr read-only bind mount not found')

    def test_command_at_end(self):
        separator = self.cmd.index('--')
        self.assertEqual(self.cmd[separator + 1:], ['/usr/bin/echo', 'hello'])

    def test_forbidden_env_not_set(self):
        config = SandboxConfig(
            workspace_dir='/tmp/test_workspace',
            socket_path='/tmp/test.sock',
            env={'SSH_AUTH_SOCK': '/tmp/bad', 'MY_VAR': 'ok'},
        )
        cmd = build_bwrap_command(config, ['/usr/bin/true'])
        # SSH_AUTH_SOCK should not appear after --setenv
        for i, arg in enumerate(cmd):
            if arg == '--setenv' and i + 1 < len(cmd):
                self.assertNotIn(cmd[i + 1], FORBIDDEN_ENV_VARS)


class TestIsForbiddenEnv(unittest.TestCase):

    def test_explicit_forbidden(self):
        self.assertTrue(is_forbidden_env('SSH_AUTH_SOCK'))
        self.assertTrue(is_forbidden_env('GITHUB_TOKEN'))
        self.assertTrue(is_forbidden_env('AWS_SECRET_ACCESS_KEY'))

    def test_prefix_forbidden(self):
        self.assertTrue(is_forbidden_env('SECRET_MY_KEY'))
        self.assertTrue(is_forbidden_env('TOKEN_SOMETHING'))
        self.assertTrue(is_forbidden_env('KEY_XYZ'))

    def test_allowed(self):
        self.assertFalse(is_forbidden_env('HOME'))
        self.assertFalse(is_forbidden_env('PATH'))
        self.assertFalse(is_forbidden_env('MY_CUSTOM_VAR'))


class TestSandboxError(unittest.TestCase):

    def test_is_exception(self):
        self.assertTrue(issubclass(SandboxError, Exception))

    def test_no_unsandboxed_fallback_in_source(self):
        """Structural test: verify no fallback patterns in launcher source."""
        import inspect
        from jarvis.sandbox import launcher
        source = inspect.getsource(launcher)
        # Must not contain patterns that suggest unsandboxed fallback
        self.assertNotIn('unsandboxed', source.lower().replace('unsandboxed execution', '').replace(
            'never run unsandboxed', '').replace('never be caught and converted to unsandboxed', ''))
        self.assertNotIn('fallback', source.lower().replace('no fallback', '').replace(
            'there is no fallback', ''))


if __name__ == '__main__':
    unittest.main()
