import sys
from tests.sandbox.helpers import run_in_sandbox

res1 = run_in_sandbox(['/usr/bin/sh', '-c', 'echo test > /etc/jarvis_test_file'])
print("ETC:", res1.returncode, res1.stderr)

res2 = run_in_sandbox(['/usr/bin/ls', '/home/dhanvanth/.ssh'])
print("SSH:", res2.returncode, res2.stderr)
