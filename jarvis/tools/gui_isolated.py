import subprocess
import tempfile
import os

import base64

def desktop_screenshot() -> list:
    """Captures a screenshot of the sandboxed GUI using grim."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    
    try:
        subprocess.run(["grim", path], check=True, capture_output=True)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return [
            {"type": "text", "text": "Isolated desktop screenshot taken."},
            {"type": "image", "data": b64, "mimeType": "image/png"}
        ]
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to capture screenshot: {e.stderr.decode('utf-8')}")
    finally:
        if os.path.exists(path):
            os.remove(path)

def desktop_windows() -> list[str]:
    """Lists all open windows in the desktop environment.

    Tries wlrctl (wlroots compositors) first, then falls back to niri msg (Niri compositor).
    Returns a list of human-readable window descriptions.
    """
    # Try wlrctl first (wlroots-based compositors)
    try:
        res = subprocess.run(
            ["wlrctl", "toplevel", "list"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    except FileNotFoundError:
        pass

    # Fallback: niri msg (Niri compositor)
    try:
        import json as _json
        res = subprocess.run(
            ["niri", "msg", "-j", "windows"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            windows = _json.loads(res.stdout)
            result = []
            for w in windows:
                focused = " (focused)" if w.get("is_focused") else ""
                result.append(
                    f"ID {w['id']}: \"{w.get('title', '')}\" "
                    f"[{w.get('app_id', 'unknown')}] "
                    f"workspace={w.get('workspace_id', '?')}{focused}"
                )
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ["Error: No supported window manager detected (need wlrctl or niri)"]

def desktop_focus(window_id: str) -> str:
    """Focuses a window by its ID.

    Tries wlrctl (wlroots compositors) first, then falls back to niri msg (Niri compositor).
    """
    # Try wlrctl first
    try:
        res = subprocess.run(
            ["wlrctl", "toplevel", "focus", window_id],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return f"Focused window '{window_id}'"
    except FileNotFoundError:
        pass

    # Fallback: niri msg (expects numeric ID)
    try:
        res = subprocess.run(
            ["niri", "msg", "action", "focus-window", "--id", str(window_id)],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return f"Focused window ID {window_id}"
        return f"Failed to focus window {window_id}: {res.stderr.strip()}"
    except FileNotFoundError:
        return "Error: No supported window manager detected (need wlrctl or niri)"

def desktop_click(x: int, y: int) -> str:
    """Clicks on the sandboxed desktop using wlrctl."""
    try:
        # Hack for absolute positioning: wlrctl pointer move is relative.
        # We move to a massive negative offset to clamp at (0,0), then move to (x, y).
        subprocess.run(["wlrctl", "pointer", "move", "-10000", "-10000"], check=True, capture_output=True)
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
