"""Test helpers for sandbox tests that run actual bwrap commands."""

import os
import shutil
import subprocess
import tempfile
import unittest

from jarvis.sandbox.launcher import SandboxConfig, build_bwrap_command


REQUIRE_BWRAP = unittest.skipUnless(
    shutil.which('bwrap'), 'bwrap not available',
)


def run_in_sandbox(
    command: list[str],
    workspace_dir: str | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run a command inside a sandbox using a temporary workspace and socket.

    Creates temporary workspace and socket paths, builds bwrap command,
    and executes it. For tests that need actual sandbox isolation.
    """
    cleanup_workspace = False
    cleanup_socket_dir = False

    if workspace_dir is None:
        workspace_dir = tempfile.mkdtemp(prefix='jarvis_test_ws_')
        cleanup_workspace = True

    socket_dir = tempfile.mkdtemp(prefix='jarvis_test_sock_')
    cleanup_socket_dir = True
    socket_path = os.path.join(socket_dir, 'mcp.sock')

    # Create a placeholder socket file so bwrap can bind-mount it
    import socket as sock_mod
    s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
    s.bind(socket_path)
    s.close()

    config = SandboxConfig(
        workspace_dir=workspace_dir,
        socket_path=socket_path,
    )

    bwrap_cmd = build_bwrap_command(config, command)

    try:
        return subprocess.run(
            bwrap_cmd, capture_output=True, text=True, timeout=timeout,
        )
    finally:
        if cleanup_workspace:
            shutil.rmtree(workspace_dir, ignore_errors=True)
        if cleanup_socket_dir:
            shutil.rmtree(socket_dir, ignore_errors=True)
