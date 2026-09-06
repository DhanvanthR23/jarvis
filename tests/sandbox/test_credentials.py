"""Sandbox credential isolation tests (G3).

Verifies that no host credentials leak into the sandbox environment.
"""

import unittest

from tests.sandbox.helpers import run_in_sandbox, REQUIRE_BWRAP


@REQUIRE_BWRAP
class TestCredentialIsolation(unittest.TestCase):

    def test_no_ssh_agent(self):
        """SSH_AUTH_SOCK must not be set in sandbox."""
        result = run_in_sandbox(['/usr/bin/sh', '-c', 'echo "${SSH_AUTH_SOCK:-UNSET}"'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'UNSET')

    def test_no_api_keys(self):
        """Common API key env vars must not be set in sandbox."""
        for var in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GITHUB_TOKEN']:
            result = run_in_sandbox(
                ['/usr/bin/sh', '-c', f'echo "${{{var}:-UNSET}}"'],
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), 'UNSET',
                             f'{var} should not be set in sandbox')

    def test_no_cloud_credentials(self):
        """Cloud credential env vars must not be set in sandbox."""
        for var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
                     'GOOGLE_APPLICATION_CREDENTIALS', 'AZURE_CLIENT_SECRET']:
            result = run_in_sandbox(
                ['/usr/bin/sh', '-c', f'echo "${{{var}:-UNSET}}"'],
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), 'UNSET',
                             f'{var} should not be set in sandbox')

    def test_env_is_minimal(self):
        """Only expected env vars should be set in sandbox."""
        result = run_in_sandbox(['/usr/bin/env'])
        self.assertEqual(result.returncode, 0)
        env_vars = {}
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, _, value = line.partition('=')
                env_vars[key] = value
        # Should only have our controlled env vars (+ PWD which sh sets)
        expected_keys = {'HOME', 'PATH', 'LANG', 'TERM', 'PWD'}
        actual_keys = set(env_vars.keys())
        unexpected = actual_keys - expected_keys
        self.assertEqual(unexpected, set(),
                         f'Unexpected env vars in sandbox: {unexpected}')


if __name__ == '__main__':
    unittest.main()
