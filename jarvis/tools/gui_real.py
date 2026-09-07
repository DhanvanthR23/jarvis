def desktop_observe() -> str:
    """Takes a mock observation of the real desktop."""
    return "Observed the real desktop"

def desktop_focus(window_id: str) -> str:
    """Mock focuses on a specific window on the real desktop."""
    return f"Focused on real window {window_id}"

def desktop_click(x: int, y: int) -> str:
    """Mock clicks on the real desktop."""
    return f"Clicked real desktop at ({x}, {y})"

def desktop_type(text: str) -> str:
    """Mock types text on the real desktop."""
    return f"Typed on real desktop: {text}"

def desktop_keypress(key: str) -> str:
    """Mock presses a key on the real desktop."""
    return f"Pressed key on real desktop: {key}"
