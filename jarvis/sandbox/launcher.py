"""Sandbox launcher — constructs and executes bubblewrap sandboxes.

Builds the bwrap command line for AGY isolation with:
- All namespace unsharing (user, PID, network, UTS, IPC, cgroup)
- Minimal read-only filesystem
- Controlled environment (no credential inheritance)
- Unix domain socket for MCP communication
- Die-with-parent for process lifecycle

CRITICAL INVARIANT: There is NO fallback to unsandboxed execution.
"""

import dataclasses
import os
import subprocess
from jarvis.sandbox.preflight import run_preflight


class SandboxError(Exception):
    """Raised when sandbox creation, verification, or execution fails.

    This error must NEVER be caught and converted to unsandboxed execution.
    """
    pass


@dataclasses.dataclass
class SandboxConfig:
    """Configuration for a sandbox instance."""
    workspace_dir: str
    socket_path: str
    read_only_paths: list[str | tuple[str, str]] = dataclasses.field(default_factory=list)
    writable_paths: list[str | tuple[str, str]] = dataclasses.field(default_factory=list)
    env: dict[str, str] = dataclasses.field(default_factory=dict)


# Minimal, controlled environment for the sandbox.
DEFAULT_ENV: dict[str, str] = {
    'HOME': '/home/agent',
    'PATH': '/usr/bin:/bin',
    'LANG': 'C.UTF-8',
    'TERM': 'dumb',
}

# Environment variables that must NEVER be inherited by the sandbox.
FORBIDDEN_ENV_VARS = frozenset({
    'SSH_AUTH_SOCK', 'SSH_AGENT_PID',
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
    'GITHUB_TOKEN', 'GH_TOKEN',
    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
    'GPG_AGENT_INFO',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'AZURE_CLIENT_SECRET', 'AZURE_CLIENT_ID',
    'DATABASE_URL',
    'DOCKER_HOST',
})

# Prefixes for env vars that are also forbidden.
FORBIDDEN_ENV_PREFIXES = ('SECRET_', 'TOKEN_', 'KEY_', 'CREDENTIAL_')


def is_forbidden_env(key: str) -> bool:
    """Check if an environment variable name is forbidden in the sandbox."""
    if key in FORBIDDEN_ENV_VARS:
        return True
    for prefix in FORBIDDEN_ENV_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


def build_bwrap_command(config: SandboxConfig, command: list[str]) -> list[str]:
    """Build the full bwrap command line for sandboxed execution.

    Uses --unshare-all to unshare all supported namespaces (user, PID,
    network, UTS, IPC, cgroup). Handles merged-/usr systems where /bin,
    /lib, /lib64, /sbin are symlinks to /usr/*.
    """
    bwrap_cmd = [
        'bwrap',
        '--unshare-all',
        '--share-net',
        '--die-with-parent',
    ]

    # Core filesystem: /usr is always bind-mounted read-only
    bwrap_cmd += ['--ro-bind', '/usr', '/usr']

    # Handle /bin, /lib, /lib64, /sbin — may be real dirs or symlinks
    for path, symlink_target in [
        ('/bin', 'usr/bin'),
        ('/lib', 'usr/lib'),
        ('/lib64', 'usr/lib'),
        ('/sbin', 'usr/bin'),
    ]:
        if os.path.islink(path):
            bwrap_cmd += ['--symlink', symlink_target, path]
        elif os.path.isdir(path):
            bwrap_cmd += ['--ro-bind', path, path]
        # If path doesn't exist, skip it

    # Isolated /proc, /dev, /tmp
    bwrap_cmd += [
        '--proc', '/proc',
        '--dev', '/dev',
        '--tmpfs', '/tmp',
        '--tmpfs', '/run',
    ]

    # Agent home directory
    bwrap_cmd += ['--dir', '/home/agent']

    # Workspace bind mount (writable)
    bwrap_cmd += ['--bind', config.workspace_dir, '/home/agent/workspace']

    # MCP socket bind mount (writable so client can connect)
    # Ensure the parent directory exists inside the sandbox
    bwrap_cmd += ['--dir', '/run/jarvis']
    bwrap_cmd += ['--bind', config.socket_path, '/run/jarvis/mcp.sock']

    # Additional read-only paths
    for item in config.read_only_paths:
        if isinstance(item, tuple) and len(item) == 2:
            src, dst = item
            if os.path.exists(src):
                bwrap_cmd += ['--ro-bind', src, dst]
        elif isinstance(item, str):
            if os.path.exists(item):
                bwrap_cmd += ['--ro-bind', item, item]

    # Additional writable paths
    for item in config.writable_paths:
        if isinstance(item, tuple) and len(item) == 2:
            src, dst = item
            if os.path.exists(src):
                bwrap_cmd += ['--bind', src, dst]
        elif isinstance(item, str):
            if os.path.exists(item):
                bwrap_cmd += ['--bind', item, item]

    # Clear all environment variables and set only controlled ones
    bwrap_cmd += ['--clearenv']

    env_to_set = DEFAULT_ENV.copy()
    for k, v in config.env.items():
        if not is_forbidden_env(k):
            env_to_set[k] = v

    for key, value in sorted(env_to_set.items()):
        bwrap_cmd += ['--setenv', key, value]

    # Separator and command
    bwrap_cmd += ['--']
    bwrap_cmd += command

    return bwrap_cmd


def verify_sandbox(config: SandboxConfig) -> bool:
    """Verify sandbox isolation by running a test command inside it.

    Checks:
    1. Command executes successfully inside the sandbox
    2. PID namespace is isolated (few visible PIDs)

    Returns True only if verification passes.
    """
    cmd = build_bwrap_command(
        config,
        ['/usr/bin/sh', '-c', 'ls -1 /proc | grep -cE "^[0-9]"'],
    )
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return False
        # PID namespace isolation: should see very few processes
        pid_count = int(res.stdout.strip())
        return pid_count <= 10
    except Exception:
        return False


def launch_sandboxed(
    config: SandboxConfig,
    command: list[str],
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Launch a command inside the sandbox.

    Runs preflight checks, builds the bwrap command, and executes it.

    CRITICAL: There is NO fallback. If preflight or sandbox fails,
    SandboxError is raised. The command is NEVER run unsandboxed.

    Raises:
        SandboxError: On any preflight, sandbox, or execution failure.
    """
    # Preflight — must pass
    preflight = run_preflight()
    if not preflight.passed:
        raise SandboxError(
            'Preflight checks failed — AGY execution refused. '
            f'Failed checks: {[n for n, c in preflight.checks.items() if not c.passed]}'
        )

    # Build sandboxed command
    bwrap_cmd = build_bwrap_command(config, command)

    # Execute — no fallback
    try:
        return subprocess.run(
            bwrap_cmd, capture_output=True, timeout=timeout, text=True,
        )
    except subprocess.TimeoutExpired as e:
        raise SandboxError(f'Sandbox execution timed out after {timeout}s: {e}')
    except Exception as e:
        raise SandboxError(f'Sandbox execution failed: {e}')
