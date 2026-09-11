"""Read-only Network capabilities."""
import subprocess


def network_interfaces() -> str:
    """Get network interfaces information."""
    res = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else "ip addr failed"

def network_status() -> str:
    """Get network routing and connection status."""
    route = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout
    ss = subprocess.run(['ss', '-tulpn'], capture_output=True, text=True).stdout
    return f"--- Routes ---\n{route}\n--- Listening Ports ---\n{ss}"
