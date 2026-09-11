

def desktop_screenshot() -> str:
    """Takes a mock screenshot of the isolated desktop."""
    return "Took a screenshot of the isolated desktop"

def desktop_windows() -> list[str]:
    """Lists mock windows in the isolated desktop."""
    return ["Mock Window 1", "Mock Window 2"]

def desktop_focus(window_id: str) -> str:
    """Mock focuses on a specific window in the isolated desktop."""
    return f"Focused on window {window_id}"

def desktop_click(x: int, y: int) -> str:
    """Mock clicks on the isolated desktop."""
    return f"Clicked at ({x}, {y})"

def desktop_type(text: str) -> str:
    """Mock types text on the isolated desktop."""
    return f"Typed: {text}"

def desktop_keypress(key: str) -> str:
    """Mock presses a key on the isolated desktop."""
    return f"Pressed key: {key}"
