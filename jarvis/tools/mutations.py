"""Controlled mutation capabilities (G18)."""
import os
import subprocess

def files_write(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', errors='replace') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

def service_restart(service: str) -> str:
    """Restart a systemd service."""
    if not service.replace('-', '').replace('_', '').isalnum():
        return "Invalid service name"
        
    res = subprocess.run(['sudo', 'systemctl', 'restart', service], capture_output=True, text=True)
    if res.returncode == 0:
        return f"Successfully restarted {service}"
    return f"Failed to restart {service}: {res.stderr}"

def package_install(package: str) -> str:
    """Install a system package using apt-get."""
    if not package.replace('-', '').replace('_', '').isalnum():
        return "Invalid package name"
        
    # Non-interactive install
    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    
    res = subprocess.run(['sudo', 'apt-get', 'install', '-y', package], capture_output=True, text=True, env=env)
    if res.returncode == 0:
        return f"Successfully installed {package}"
    return f"Failed to install {package}: {res.stderr}"
