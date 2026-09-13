import tempfile
import os
import subprocess
import pytest
from jarvis.sandbox.launcher import SandboxConfig, launch_sandboxed
from tests.sandbox.helpers import REQUIRE_BWRAP

@REQUIRE_BWRAP
def test_gui_isolated_wayland_display():
    with tempfile.TemporaryDirectory() as workspace_dir:
        socket_path = os.path.join(workspace_dir, "mcp.sock")
        # Ensure the socket directory exists or touch the file
        open(socket_path, 'w').close()
        
        config = SandboxConfig(
            workspace_dir=workspace_dir,
            socket_path=socket_path,
            compositor='cage',
            enable_gpu=False
        )
        
        # We run printenv to see if WAYLAND_DISPLAY is set by cage
        res = launch_sandboxed(config, ['sh', '-c', 'echo WAYLAND_DISPLAY=$WAYLAND_DISPLAY'])
        assert 'WAYLAND_DISPLAY=' in res.stdout
        assert res.stdout.strip() != 'WAYLAND_DISPLAY='

@REQUIRE_BWRAP
def test_desktop_screenshot_in_sandbox():
    with tempfile.TemporaryDirectory() as workspace_dir:
        socket_path = os.path.join(workspace_dir, "mcp.sock")
        open(socket_path, 'w').close()
        
        config = SandboxConfig(
            workspace_dir=workspace_dir,
            socket_path=socket_path,
            compositor='cage',
            enable_gpu=False,
            read_only_paths=[("/home/dhanvanth/projects/jarvis", "/home/dhanvanth/projects/jarvis")]
        )
        
        script = '''
import sys
import os
sys.path.insert(0, "/home/dhanvanth/projects/jarvis")
from jarvis.tools.gui_isolated import desktop_screenshot

try:
    path = desktop_screenshot()
    if not os.path.exists(path):
        print("FAIL: Path does not exist")
        sys.exit(1)
    if os.path.getsize(path) == 0:
        print("FAIL: File is empty")
        sys.exit(1)
    print("SUCCESS")
    os.remove(path)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
'''
        script_path = os.path.join(workspace_dir, "test_screenshot.py")
        with open(script_path, 'w') as f:
            f.write(script)
            
        res = launch_sandboxed(config, ['python3', '/home/agent/workspace/test_screenshot.py'])
        assert "SUCCESS" in res.stdout, f"Screenshot failed: {res.stdout} {res.stderr}"

from unittest.mock import patch
from jarvis.tools.gui_isolated import desktop_type, desktop_keypress, desktop_click

@patch("subprocess.run")
def test_desktop_type_isolated(mock_run):
    res = desktop_type("hello")
    mock_run.assert_called_once_with(["wtype", "hello"], check=True, capture_output=True)
    assert res == "Typed on isolated desktop: hello"

@patch("subprocess.run")
def test_desktop_keypress_isolated(mock_run):
    res = desktop_keypress("Return")
    mock_run.assert_called_once_with(["wtype", "-k", "Return"], check=True, capture_output=True)
    assert res == "Pressed key on isolated desktop: Return"

@patch("subprocess.run")
def test_desktop_click_isolated(mock_run):
    res = desktop_click(100, 200)
    assert mock_run.call_count == 2
    mock_run.assert_any_call(["wlrctl", "pointer", "move", "100", "200"], check=True, capture_output=True)
    mock_run.assert_any_call(["wlrctl", "pointer", "click", "left"], check=True, capture_output=True)
    assert res == "Clicked isolated desktop at (100, 200)"
