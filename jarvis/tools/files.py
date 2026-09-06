"""Read-only Files capabilities."""
import os
import subprocess

def files_read(path: str) -> str:
    """Read contents of a file."""
    if not os.path.exists(path):
        return f"File {path} does not exist"
    if not os.path.isfile(path):
        return f"Path {path} is not a file"
    try:
        with open(path, 'r', errors='replace') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def files_search(directory: str, pattern: str) -> str:
    """Search for files in a directory matching a pattern."""
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return f"Directory {directory} does not exist"
        
    cmd = ['find', directory, '-type', 'f', '-name', pattern]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else f"find failed: {res.stderr}"
