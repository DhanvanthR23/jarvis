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


def browser_navigate(browser, url: str):
    """
    Navigates to a URL. Opens a new page and goes to the URL.
    Returns the new page.
    """
    page = browser.new_page()
    page.goto(url)
    return page

def browser_read(page):
    """
    Extracts the DOM inner text and accessibility tree from the current page.
    """
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

def browser_type(page, selector: str, text: str):
    """
    Types text into the specified selector on the page.
    """
    page.fill(selector, text)

def browser_click(page, selector: str):
    """
    Clicks on the specified selector on the page.
    """
    page.click(selector)

def browser_download(page, selector: str, download_path: str):
    """
    Clicks a selector to initiate a download and saves it to download_path.
    """
    if not is_safe_path(download_path):
        raise ValueError(f"Path {download_path} is outside the allowed workspace.")
    with page.expect_download() as download_info:
        page.click(selector)
    download = download_info.value
    download.save_as(download_path)

def browser_upload(page, selector: str, upload_path: str):
    """
    Uploads a file at upload_path to the specified input element.
    """
    if not is_safe_path(upload_path):
        raise ValueError(f"Path {upload_path} is outside the allowed workspace.")
    page.set_input_files(selector, upload_path)

def cleanup_browser(playwright, browser, page=None):
    """
    Cleans up browser instances properly to validate memory usage.
    """
    if page:
        try:
            page.close()
        except Exception as e:
            logger.error(f"Error closing page: {e}")
    if browser:
        try:
            browser.close()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    if playwright:
        try:
            playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping playwright: {e}")

def browser_search(query: str):
    """
    Performs a Google search for the query and returns the top results.
    Creates and tears down its own browser instance.
    """
    playwright = None
    browser = None
    page = None
    try:
        playwright, browser = launch_browser()
        page = browser.new_page()
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        page.goto(f"https://html.duckduckgo.com/html/?q={encoded_query}")
        
        results = page.evaluate('''() => {
            const items = document.querySelectorAll('.result');
            const data = [];
            for (let i = 0; i < Math.min(items.length, 5); i++) {
                const titleEl = items[i].querySelector('.result__title');
                const snippetEl = items[i].querySelector('.result__snippet');
                const urlEl = items[i].querySelector('.result__url');
                if (titleEl && urlEl) {
                    data.push({
                        title: titleEl.innerText,
                        snippet: snippetEl ? snippetEl.innerText : '',
                        url: urlEl.getAttribute('href') || urlEl.innerText
                    });
                }
            }
            return data;
        }''')
        
        return results
    except Exception as e:
        return f"Browser search failed: {e}"
    finally:
        cleanup_browser(playwright, browser, page)
