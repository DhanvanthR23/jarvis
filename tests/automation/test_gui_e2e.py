import tempfile
import os
import pytest
from jarvis.sandbox.launcher import SandboxConfig, launch_sandboxed
from tests.sandbox.helpers import REQUIRE_BWRAP

@REQUIRE_BWRAP
def test_gui_app_e2e():
    """E2E test verifying agent can launch GUI, screenshot, and type/click."""
    with tempfile.TemporaryDirectory() as workspace_dir:
        socket_path = os.path.join(workspace_dir, "mcp.sock")
        open(socket_path, 'w').close()
        
        # Create dummy wlrctl and wtype
        bin_dir = os.path.join(workspace_dir, "bin")
        os.makedirs(bin_dir)
        
        with open(os.path.join(bin_dir, "wlrctl"), "w") as f:
            f.write("#!/bin/sh\necho 'wlrctl executed'\nexit 0\n")
        os.chmod(os.path.join(bin_dir, "wlrctl"), 0o755)
        
        with open(os.path.join(bin_dir, "wtype"), "w") as f:
            f.write("#!/bin/sh\necho 'wtype executed'\nexit 0\n")
        os.chmod(os.path.join(bin_dir, "wtype"), 0o755)
        
        config = SandboxConfig(
            workspace_dir=workspace_dir,
            socket_path=socket_path,
            compositor='cage',
            enable_gpu=False,
            read_only_paths=[("/home/dhanvanth/projects/jarvis", "/home/dhanvanth/projects/jarvis")],
            env={'PATH': '/home/agent/workspace/bin:/usr/bin:/bin'}
        )
        
        script = '''
import sys
import os
import subprocess
import time

sys.path.insert(0, "/home/dhanvanth/projects/jarvis")
from jarvis.tools.gui_isolated import desktop_screenshot, desktop_click, desktop_type

try:
    # Launch a basic GUI app in the background (zenity)
    proc = subprocess.Popen(["zenity", "--info", "--text", "Hello GUI"])
    
    # Wait for GUI to appear
    time.sleep(1.0)
    
    # 1. Take screenshot
    path = desktop_screenshot()
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        print("FAIL: Screenshot invalid")
        sys.exit(1)
        
    # 2. Perform a click
    click_res = desktop_click(100, 100)
    if "Clicked isolated desktop" not in click_res:
        print("FAIL: Click failed")
        sys.exit(1)
        
    # 3. Perform a type
    type_res = desktop_type("test typing")
    if "Typed on isolated desktop" not in type_res:
        print("FAIL: Type failed")
        sys.exit(1)
        
    proc.terminate()
    print("SUCCESS")
    os.remove(path)
except Exception as e:
    print(f"FAIL: Exception {e}")
    sys.exit(1)
'''
        script_path = os.path.join(workspace_dir, "test_run.py")
        with open(script_path, 'w') as f:
            f.write(script)
            
        res = launch_sandboxed(config, ['python3', '/home/agent/workspace/test_run.py'])
        assert "SUCCESS" in res.stdout, f"E2E Test failed: stdout={res.stdout}, stderr={res.stderr}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
