"""Read-only Logs capabilities."""
import subprocess

def logs_search(service: str = None, grep: str = None, lines: int = 50) -> str:
    """Search system logs using journalctl.
    
    Args:
        service: Optional systemd service name (e.g. 'ssh.service')
        grep: Optional regex to filter logs
        lines: Number of recent lines to return
    """
    cmd = ['journalctl', '--no-pager', '-n', str(lines)]
    if service:
        cmd.extend(['-u', service])
    if grep:
        cmd.extend(['--grep', grep])
        
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else "journalctl failed or found no logs"
