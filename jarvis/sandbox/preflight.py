"""Host capability preflight — verifies the system can support the intended sandbox.

Checks bubblewrap availability, namespace support, and Unix socket capability.
A FAIL result means AGY startup is disabled (fail-closed).
"""

import dataclasses
import os
import shutil
import socket
import subprocess
import tempfile


@dataclasses.dataclass
class CheckResult:
    """Result of a single preflight check."""
    name: str
    passed: bool
    detail: str


@dataclasses.dataclass
class PreflightResult:
    """Aggregate result of all preflight checks."""
    passed: bool
    checks: dict[str, CheckResult]


def _run_bwrap_test(args: list[str], description: str) -> CheckResult:
    """Run a bwrap test command and return a CheckResult.

    Uses --unshare-all with a minimal filesystem to test namespace support.
    On merged-/usr systems (where /bin -> usr/bin etc.), uses --symlink
    instead of --ro-bind for the symlinked paths.
    """
    # Build minimal filesystem arguments that work on both merged and
    # non-merged /usr systems.
    fs_args = ['--ro-bind', '/usr', '/usr']

    for path, target in [('/bin', 'usr/bin'), ('/lib', 'usr/lib'),
                         ('/lib64', 'usr/lib'), ('/sbin', 'usr/bin')]:
        if os.path.islink(path):
            fs_args += ['--symlink', target, path]
        elif os.path.isdir(path):
            fs_args += ['--ro-bind', path, path]

    fs_args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']

    cmd = ['bwrap'] + args + fs_args + ['--', '/usr/bin/true']
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=10)
        if res.returncode == 0:
            return CheckResult(description, True, 'Success')
        else:
            stderr = res.stderr.decode('utf-8', errors='replace').strip()
            return CheckResult(description, False, stderr or f'exit code {res.returncode}')
    except FileNotFoundError:
        return CheckResult(description, False, 'bwrap binary not found')
    except subprocess.TimeoutExpired:
        return CheckResult(description, False, 'timeout')
    except Exception as e:
        return CheckResult(description, False, str(e))


def run_preflight() -> PreflightResult:
    """Run all preflight checks and return aggregate result.

    Returns PreflightResult with passed=True only if ALL checks pass.
    """
    checks: dict[str, CheckResult] = {}

    # 1. bwrap available
    bwrap_path = shutil.which('bwrap')
    checks['bwrap_available'] = CheckResult(
        'bwrap_available',
        bwrap_path is not None,
        f'Found at {bwrap_path}' if bwrap_path else 'bwrap not found in PATH',
    )

    # If bwrap isn't available, the remaining checks will fail,
    # but we still run them for completeness of the report.

    # 2. User namespace
    userns_sysctl = '/proc/sys/kernel/unprivileged_userns_clone'
    if os.path.exists(userns_sysctl):
        try:
            with open(userns_sysctl) as f:
                val = f.read().strip()
            if val == '1':
                checks['user_namespace'] = CheckResult(
                    'user_namespace', True, 'Enabled via sysctl')
            else:
                checks['user_namespace'] = CheckResult(
                    'user_namespace', False,
                    f'unprivileged_userns_clone = {val} (need 1)')
        except Exception as e:
            checks['user_namespace'] = CheckResult(
                'user_namespace', False, str(e))
    else:
        # sysctl file absent — test empirically
        checks['user_namespace'] = _run_bwrap_test(
            ['--unshare-user'], 'user_namespace')

    # 3. PID namespace (uses --unshare-user --unshare-pid)
    checks['pid_namespace'] = _run_bwrap_test(
        ['--unshare-user', '--unshare-pid'], 'pid_namespace')

    # 4. Network namespace (uses --unshare-user --unshare-net)
    checks['network_namespace'] = _run_bwrap_test(
        ['--unshare-user', '--unshare-net'], 'network_namespace')

    # 5. Full isolation (--unshare-all, which implies user + pid + net + uts + ipc + cgroup)
    checks['full_isolation'] = _run_bwrap_test(
        ['--unshare-all'], 'full_isolation')

    # 6. Unix domain socket creation
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, 'test.sock')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(sock_path)
            finally:
                sock.close()
            checks['unix_socket'] = CheckResult(
                'unix_socket', True, 'Created and closed successfully')
    except Exception as e:
        checks['unix_socket'] = CheckResult(
            'unix_socket', False, str(e))

    all_passed = all(c.passed for c in checks.values())

    result = PreflightResult(passed=all_passed, checks=checks)

    # Print clear output
    print(f'Sandbox prerequisites: {"PASS" if all_passed else "FAIL"}')
    for name, check in checks.items():
        status = 'PASS' if check.passed else 'FAIL'
        print(f'  {name}: {status} — {check.detail}')
    if not all_passed:
        print('AGY startup disabled.')

    return result
