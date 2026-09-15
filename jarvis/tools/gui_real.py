import os
import time
import subprocess
import tempfile
import base64

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_LAST_SCREENSHOT_TIME = 0.0
MIN_INTERVAL = 2.0  # max 1 screenshot per 2 seconds

class WaylandProxyError(Exception):
    pass

class RateLimitError(Exception):
    pass

def _verify_wayland_proxy():
    # Require a proxy. If WAYLAND_DISPLAY is raw wayland-0, refuse.
    display = os.environ.get("WAYLAND_DISPLAY", "")
    if not display:
        raise WaylandProxyError("WAYLAND_DISPLAY is not set.")
    
    # We require the display to be a proxy. 
    if display == "wayland-0":
        raise WaylandProxyError("Raw WAYLAND_DISPLAY (wayland-0) is not allowed. A filtering proxy is required (whitelist: screencopy, virtual-keyboard, virtual-pointer).")

def desktop_observe() -> list:
    """Takes an observation of the real desktop using grim via a Wayland proxy."""
    global _LAST_SCREENSHOT_TIME
    
    _verify_wayland_proxy()
    
    now = time.time()
    if now - _LAST_SCREENSHOT_TIME < MIN_INTERVAL:
        raise RateLimitError(f"Screenshot frequency exceeded. Max 1 every {MIN_INTERVAL} seconds.")
    
    _LAST_SCREENSHOT_TIME = now
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
        
    try:
        # Run grim restricted
        subprocess.run(["grim", "-t", "png", tmp_path], check=True, capture_output=True)
        
        # Optimize image if PIL is available
        if HAS_PIL:
            try:
                with Image.open(tmp_path) as img:
                    img.thumbnail((1920, 1080), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(tmp_path, "JPEG", quality=85, optimize=True)
            except Exception:
                pass
                
        # Return MCP-compatible content block
        with open(tmp_path, "rb") as img:
            b64 = base64.b64encode(img.read()).decode("utf-8")
        
        return [
            {"type": "text", "text": "Real desktop screenshot taken."},
            {"type": "image", "data": b64, "mimeType": "image/jpeg" if HAS_PIL else "image/png"}
        ]
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"grim failed: {e.stderr.decode('utf-8', errors='ignore')}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

desktop_observe.required_capabilities = ["CAP_WAYLAND_OBSERVE"]

def desktop_focus(window_id: str) -> str:
    """Focuses a window on the real desktop by its ID.

    Tries niri msg first (Niri compositor), then falls back to wlrctl (wlroots).
    Requires a Wayland proxy to be active.
    """
    _verify_wayland_proxy()

    # Try niri msg first (native for the user's compositor)
    try:
        res = subprocess.run(
            ["niri", "msg", "action", "focus-window", "--id", str(window_id)],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return f"Focused real window ID {window_id}"
    except FileNotFoundError:
        pass

    # Fallback: wlrctl (wlroots-based compositors)
    try:
        res = subprocess.run(
            ["wlrctl", "toplevel", "focus", window_id],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return f"Focused real window '{window_id}'"
        return f"Failed to focus window {window_id}: {res.stderr.strip()}"
    except FileNotFoundError:
        return "Error: No supported window manager detected (need niri or wlrctl)"

desktop_focus.required_capabilities = ["CAP_WAYLAND_CONTROL"]

def desktop_click(x: int, y: int) -> str:
    """Clicks on the real desktop using wlrctl."""
    _verify_wayland_proxy()
    try:
        # Hack for absolute positioning: wlrctl pointer move is relative.
        # We move to a massive negative offset to clamp at (0,0), then move to (x, y).
        subprocess.run(["wlrctl", "pointer", "move", "-10000", "-10000"], check=True, capture_output=True)
        subprocess.run(["wlrctl", "pointer", "move", str(x), str(y)], check=True, capture_output=True)
        subprocess.run(["wlrctl", "pointer", "click", "left"], check=True, capture_output=True)
        return f"Clicked real desktop at ({x}, {y})"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"wlrctl failed: {e.stderr.decode('utf-8', errors='ignore')}")

desktop_click.required_capabilities = ["CAP_WAYLAND_CONTROL"]

def desktop_type(text: str) -> str:
    """Types text on the real desktop using wtype."""
    _verify_wayland_proxy()
    try:
        subprocess.run(["wtype", text], check=True, capture_output=True)
        return f"Typed on real desktop: {text}"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"wtype failed: {e.stderr.decode('utf-8', errors='ignore')}")

desktop_type.required_capabilities = ["CAP_WAYLAND_CONTROL"]

def desktop_keypress(key: str) -> str:
    """Presses a key on the real desktop using wtype."""
    _verify_wayland_proxy()
    try:
        subprocess.run(["wtype", "-k", key], check=True, capture_output=True)
        return f"Pressed key on real desktop: {key}"
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"wtype failed: {e.stderr.decode('utf-8', errors='ignore')}")

desktop_keypress.required_capabilities = ["CAP_WAYLAND_CONTROL"]
