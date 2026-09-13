import subprocess
import tempfile
import os

def desktop_screenshot() -> str:
    """Captures a screenshot of the sandboxed GUI using grim."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    
    try:
        subprocess.run(["grim", path], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to capture screenshot: {e.stderr.decode('utf-8')}")
        
    return path

def desktop_windows() -> list[str]:
    raise NotImplementedError("To be implemented in G21.2")

def desktop_focus(window_id: str) -> str:
    raise NotImplementedError("To be implemented in G21.2")

def desktop_click(x: int, y: int) -> str:
    """Clicks on the sandboxed desktop using wlrctl."""
    try:
        subprocess.run(["wlrctl", "pointer", "move", str(x), str(y)], check=True, capture_output=True)
        subprocess.run(["wlrctl", "pointer", "click", "left"], check=True, capture_output=True)
        return f"Clicked isolated desktop at ({x}, {y})"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to click: {e.stderr.decode('utf-8', errors='ignore')}")

def desktop_type(text: str) -> str:
    """Types text on the sandboxed desktop using wtype."""
    try:
        subprocess.run(["wtype", text], check=True, capture_output=True)
        return f"Typed on isolated desktop: {text}"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to type: {e.stderr.decode('utf-8', errors='ignore')}")

def desktop_keypress(key: str) -> str:
    """Presses a key on the sandboxed desktop using wtype."""
    try:
        subprocess.run(["wtype", "-k", key], check=True, capture_output=True)
        return f"Pressed key on isolated desktop: {key}"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to press key: {e.stderr.decode('utf-8', errors='ignore')}")
