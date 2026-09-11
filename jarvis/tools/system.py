"""Read-only Linux capabilities (G17).

Provides structured access to system information without arbitrary shell execution.
"""
import os
import subprocess


def system_info() -> dict:
    """Get basic system information."""
    uname = subprocess.run(['uname', '-a'], capture_output=True, text=True).stdout.strip()
    os_release = {}
    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    os_release[k] = v.strip('"\'')
    return {
        "uname": uname,
        "os_release": os_release
    }

def system_temperature() -> dict:
    """Get system temperature readings."""
    temps = {}
    zone_dir = '/sys/class/thermal/'
    if os.path.exists(zone_dir):
        for zone in os.listdir(zone_dir):
            if zone.startswith('thermal_zone'):
                try:
                    with open(os.path.join(zone_dir, zone, 'type')) as f:
                        t_type = f.read().strip()
                    with open(os.path.join(zone_dir, zone, 'temp')) as f:
                        t_temp = int(f.read().strip()) / 1000.0
                    temps[t_type] = t_temp
                except Exception:
                    pass
    return {"temperatures_celsius": temps}
