"""Fail-closed secure launcher (G5).

The ONLY legal states:
  SANDBOX VERIFIED → AGY starts
  anything else    → AGY doesn't start (SandboxError raised)

There is ZERO code that executes a command without the sandbox.
No try/except fallback. No debug mode. No dev mode. No bypass.
"""

import subprocess

from jarvis.sandbox.preflight import run_preflight
from jarvis.sandbox.launcher import (
    SandboxConfig,
    SandboxError,
    build_bwrap_command,
    verify_sandbox,
)


class SecureLauncher:
    """Fail-closed launcher: preflight → build → verify → execute.

    INVARIANT: If any step fails, SandboxError is raised.
    The command is NEVER executed without sandbox isolation.
    """

    def __init__(self, config: SandboxConfig):
        self.config = config

    def launch(
        self, command: list[str], timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        """Launch a command inside a verified sandbox.

        Steps:
        1. Run preflight checks — must all pass
        2. Build the bwrap command
        3. Verify sandbox isolation
        4. Execute the command

        Raises SandboxError on ANY failure. No fallback.
        """
        # Step 1: Preflight — must pass
        preflight_result = run_preflight()
        if not preflight_result.passed:
            failed = [
                name for name, check in preflight_result.checks.items()
                if not check.passed
            ]
            raise SandboxError(
                f'Preflight failed: {failed}. AGY execution refused.'
            )

        # Step 2: Build sandboxed command
        bwrap_cmd = build_bwrap_command(self.config, command)

        # Step 3: Verify sandbox isolation
        if not verify_sandbox(self.config):
            raise SandboxError(
                'Sandbox verification failed. AGY execution refused.'
            )

        # Step 4: Execute inside sandbox — no fallback
        try:
            return subprocess.run(
                bwrap_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise SandboxError(f'Sandbox execution timed out: {e}')
        except Exception as e:
            raise SandboxError(f'Sandbox execution failed: {e}')
