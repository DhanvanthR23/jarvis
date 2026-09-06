"""Read-only Processes capabilities."""
import subprocess

def processes_list() -> str:
    """List running processes."""
    res = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else "ps aux failed"
