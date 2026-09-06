"""Command execution capabilities (Phase 22, Level 2).

Provides allowlisted, structured command execution.
"""
import subprocess
from typing import List

# Level 2 allowlist (strict base commands)
ALLOWLIST = {
    'ping',
    'df',
    'free',
    'ls',
    'cat',
    'grep',
    'uptime',
    'dmesg',
    'nmcli',    # Wi-Fi / network
    'rfkill',   # Bluetooth / wireless
    'bluetoothctl',
    'lscpu',
    'lsusb',
    'lspci',
    'systemctl' # Status queries only, mutations are via service.restart
}

def command_execute(command: str, args: List[str] = None) -> str:
    """Execute an allowlisted command with structured arguments."""
    if command not in ALLOWLIST:
        return f"Error: Command '{command}' is not in the allowlist."
        
    args = args or []
    
    # Extra safety: prevent systemctl mutations through this generic tool
    if command == 'systemctl' and any(arg in args for arg in ['start', 'stop', 'restart', 'enable', 'disable', 'reload']):
        return "Error: Use the service.restart tool for service mutations."

    cmd_list = [command] + args
    
    try:
        # Use subprocess.run without shell=True for structured safety
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
        output = res.stdout
        if res.stderr:
            output += f"\nSTDERR:\n{res.stderr}"
        return output if output else f"Command '{command}' executed successfully with no output."
    except Exception as e:
        return f"Execution error: {str(e)}"
