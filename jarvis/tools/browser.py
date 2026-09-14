import subprocess
import logging
import os

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None

logger = logging.getLogger(__name__)

class SandboxSupportError(Exception):
    pass

class BrowserSetupError(Exception):
    pass

def is_safe_path(path: str) -> bool:
    """Check if the given path is within the sandboxed workspace."""
    workspace = os.environ.get('WORKSPACE_DIR', '/home/agent/workspace')
    resolved_path = os.path.abspath(path)
    resolved_workspace = os.path.abspath(workspace)
    # Adding os.sep ensures that we don't match /home/agent/workspace_other
    if not resolved_workspace.endswith(os.sep):
        resolved_workspace += os.sep
    return resolved_path.startswith(resolved_workspace) or resolved_path == resolved_workspace[:-1]

def check_sandbox_support() -> bool:
    """Checks if unprivileged user namespaces are supported by trying to run a basic unshare command."""
    try:
        result = subprocess.run(
            ["unshare", "--user", "--pid", "echo", "test"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0 and "test" in result.stdout
    except Exception as e:
        logger.error(f"Sandbox check failed: {e}")
        return False

def launch_browser():
    """
    Initializes and returns a headless Playwright browser instance.
    Enforces nested unprivileged user namespaces.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise BrowserSetupError("Playwright is not installed.")

    if not check_sandbox_support():
        raise SandboxSupportError("Nested unprivileged user namespaces are required but not supported.")

    playwright = sync_playwright().start()
    try:
        # We explicitly avoid --no-sandbox here. Playwright-managed chromium.
        browser = playwright.chromium.launch(headless=True)
        return playwright, browser
    except Exception as e:
        playwright.stop()
        raise BrowserSetupError(f"Failed to launch browser: {e}")


_playwright = None
_browser = None
_current_page = None

def _ensure_browser():
    global _playwright, _browser, _current_page
    if not PLAYWRIGHT_AVAILABLE:
        raise BrowserSetupError("Playwright is not installed.")
    if _browser is None:
        if not check_sandbox_support():
            raise SandboxSupportError("Nested unprivileged user namespaces are required but not supported.")
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
    if _current_page is None or _current_page.is_closed():
        _current_page = _browser.new_page()
    return _current_page

def browser_navigate(url: str):
    """
    Navigates to a URL. Opens a new page and goes to the URL.
    Returns the page title.
    """
    page = _ensure_browser()
    page.goto(url)
    return page.title()

def browser_read():
    """
    Extracts the DOM inner text and accessibility tree from the current page.
    """
    page = _ensure_browser()
    try:
        ax_tree = page.accessibility.snapshot()
    except Exception:
        ax_tree = None
        
    return {
        "title": page.title(),
        "url": page.url,
        "text_content": page.evaluate("document.body.innerText || ''"),
        "accessibility_tree": ax_tree
    }

def browser_type(selector: str, text: str):
    """
    Types text into the specified selector on the page.
    """
    page = _ensure_browser()
    page.fill(selector, text)
    return f"Typed '{text}' into '{selector}'"

def browser_click(selector: str):
    """
    Clicks on the specified selector on the page.
    """
    page = _ensure_browser()
    page.click(selector)
    return f"Clicked '{selector}'"

def browser_download(selector: str, download_path: str):
    """
    Clicks a selector to initiate a download and saves it to download_path.
    """
    if not is_safe_path(download_path):
        raise ValueError(f"Path {download_path} is outside the allowed workspace.")
    page = _ensure_browser()
    with page.expect_download() as download_info:
        page.click(selector)
    download = download_info.value
    download.save_as(download_path)
    return f"Downloaded to '{download_path}'"

def browser_upload(selector: str, upload_path: str):
    """
    Uploads a file at upload_path to the specified input element.
    """
    if not is_safe_path(upload_path):
        raise ValueError(f"Path {upload_path} is outside the allowed workspace.")
    page = _ensure_browser()
    page.set_input_files(selector, upload_path)
    return f"Uploaded '{upload_path}' to '{selector}'"

def cleanup_browser():
    """
    Cleans up browser instances properly to validate memory usage.
    """
    global _playwright, _browser, _current_page
    if _current_page:
        try:
            _current_page.close()
        except Exception:
            pass
        _current_page = None
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None

def browser_search(query: str):
    """
    Performs a web search for the query and returns the top results.
    If you need detailed up-to-date info from one of the results, use browser_navigate and browser_read on its URL.
    """
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=5):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
            return results
    except ImportError:
        return "Search failed: ddgs library is not installed. Please install it with 'pip install ddgs'."
    except Exception as e:
        return f"Browser search failed: {e}"
