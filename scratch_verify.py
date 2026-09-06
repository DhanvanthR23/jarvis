import os
from jarvis.sandbox.launcher import SandboxConfig, verify_sandbox, build_bwrap_command
import tempfile
import subprocess

ws = tempfile.mkdtemp()
cf = tempfile.mkdtemp()
sock_path = os.path.join(cf, 'mcp.sock')
open(sock_path, 'w').close()

import shutil
agy_path = shutil.which('agy')

config = SandboxConfig(
    workspace_dir=ws,
    socket_path=sock_path,
    read_only_paths=[(cf, '/home/agent/.gemini'), (agy_path, '/usr/bin/agy')]
)
cmd = build_bwrap_command(config, ['/usr/bin/sh', '-c', 'ls -1 /proc | grep -cE "^[0-9]"'])
print("CMD:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)
print("RETURNCODE:", res.returncode)
