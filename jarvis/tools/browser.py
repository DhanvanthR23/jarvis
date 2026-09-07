"""Mock browser automation tools."""

def browser_navigate(url: str) -> str:
    """Navigates to the specified URL."""
    return f"Navigated to {url}"

def browser_read(selector: str = "") -> str:
    """Reads content from the page, optionally filtered by a selector."""
    if selector:
        return f"Read content from selector {selector}"
    return "Read content from page"

def browser_click(selector: str) -> str:
    """Clicks the element identified by the selector."""
    return f"Clicked element {selector}"

def browser_type(selector: str, text: str) -> str:
    """Types text into the element identified by the selector."""
    return f"Typed '{text}' into element {selector}"

def browser_download(url: str, path: str) -> str:
    """Downloads a file from the URL to the specified path."""
    return f"Downloaded {url} to {path}"

def browser_upload(selector: str, path: str) -> str:
    """Uploads a file from the specified path using the file input selector."""
    return f"Uploaded {path} via {selector}"
