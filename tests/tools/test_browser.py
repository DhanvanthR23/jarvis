"""Tests for browser tools."""
import unittest
from unittest.mock import patch, MagicMock

import jarvis.tools.browser as browser_module
from jarvis.tools.browser import (
    check_sandbox_support,
    launch_browser,
    SandboxSupportError,
    BrowserSetupError
)

class TestBrowser(unittest.TestCase):
    @patch('subprocess.run')
    def test_check_sandbox_support_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test\n"
        mock_run.return_value = mock_result
        
        self.assertTrue(check_sandbox_support())
        mock_run.assert_called_with(
            ["unshare", "--user", "--pid", "echo", "test"],
            capture_output=True,
            text=True,
            timeout=2
        )

    @patch('subprocess.run')
    def test_check_sandbox_support_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result
        
        self.assertFalse(check_sandbox_support())

    @patch('jarvis.tools.browser.check_sandbox_support')
    def test_launch_browser_no_sandbox(self, mock_check):
        mock_check.return_value = False
        original_avail = browser_module.PLAYWRIGHT_AVAILABLE
        browser_module.PLAYWRIGHT_AVAILABLE = True
        try:
            with self.assertRaisesRegex(SandboxSupportError, "not supported"):
                launch_browser()
        finally:
            browser_module.PLAYWRIGHT_AVAILABLE = original_avail

    def test_launch_browser_no_playwright(self):
        original_avail = browser_module.PLAYWRIGHT_AVAILABLE
        browser_module.PLAYWRIGHT_AVAILABLE = False
        try:
            with self.assertRaisesRegex(BrowserSetupError, "not installed"):
                launch_browser()
        finally:
            browser_module.PLAYWRIGHT_AVAILABLE = original_avail

    @patch('jarvis.tools.browser.sync_playwright')
    @patch('jarvis.tools.browser.check_sandbox_support')
    def test_launch_browser_success(self, mock_check, mock_sync_playwright):
        mock_check.return_value = True
        
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_sync_playwright.return_value.start.return_value = mock_playwright
        
        original_avail = browser_module.PLAYWRIGHT_AVAILABLE
        browser_module.PLAYWRIGHT_AVAILABLE = True
        try:
            p, b = launch_browser()
            self.assertEqual(p, mock_playwright)
            self.assertEqual(b, mock_browser)
            mock_playwright.chromium.launch.assert_called_with(headless=True)
        finally:
            browser_module.PLAYWRIGHT_AVAILABLE = original_avail


    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_navigate(self, mock_ensure):
        mock_page = MagicMock()
        mock_page.title.return_value = "Title"
        mock_ensure.return_value = mock_page
        
        title = browser_module.browser_navigate("http://example.com")
        self.assertEqual(title, "Title")
        mock_page.goto.assert_called_once_with("http://example.com")

    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_read(self, mock_ensure):
        mock_page = MagicMock()
        mock_page.title.return_value = "Test Title"
        mock_page.url = "http://example.com"
        mock_page.evaluate.return_value = "Test Content"
        mock_page.accessibility.snapshot.return_value = {"role": "WebArea"}
        mock_ensure.return_value = mock_page
        
        result = browser_module.browser_read()
        self.assertEqual(result["title"], "Test Title")
        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["text_content"], "Test Content")
        self.assertEqual(result["accessibility_tree"], {"role": "WebArea"})

    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_type(self, mock_ensure):
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        browser_module.browser_type("#search", "hello")
        mock_page.fill.assert_called_once_with("#search", "hello")

    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_click(self, mock_ensure):
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        browser_module.browser_click("#button")
        mock_page.click.assert_called_once_with("#button")

    def test_cleanup_browser(self):
        browser_module._playwright = MagicMock()
        browser_module._browser = MagicMock()
        browser_module._current_page = MagicMock()
        
        p = browser_module._playwright
        b = browser_module._browser
        page = browser_module._current_page
        
        browser_module.cleanup_browser()
        
        page.close.assert_called_once()
        b.close.assert_called_once()
        p.stop.assert_called_once()

    @patch('os.environ.get')
    def test_is_safe_path(self, mock_env):
        mock_env.return_value = '/home/agent/workspace'
        self.assertTrue(browser_module.is_safe_path('/home/agent/workspace/file.txt'))
        self.assertTrue(browser_module.is_safe_path('/home/agent/workspace/dir/file.txt'))
        self.assertTrue(browser_module.is_safe_path('/home/agent/workspace'))
        
        self.assertFalse(browser_module.is_safe_path('/home/agent/workspaces'))
        self.assertFalse(browser_module.is_safe_path('/etc/passwd'))
        self.assertFalse(browser_module.is_safe_path('/home/agent/workspace/../secret.txt'))

    @patch('jarvis.tools.browser.is_safe_path')
    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_download(self, mock_ensure, mock_is_safe):
        mock_is_safe.return_value = True
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        mock_download = MagicMock()
        mock_page.expect_download.return_value.__enter__.return_value.value = mock_download
        
        browser_module.browser_download("#download-btn", "/path/to/download.txt")
        mock_page.click.assert_called_once_with("#download-btn")
        mock_download.save_as.assert_called_once_with("/path/to/download.txt")

    @patch('jarvis.tools.browser.is_safe_path')
    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_download_unsafe(self, mock_ensure, mock_is_safe):
        mock_is_safe.return_value = False
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        
        with self.assertRaisesRegex(ValueError, "outside the allowed workspace"):
            browser_module.browser_download("#download-btn", "/unsafe/path.txt")
        
        mock_page.click.assert_not_called()

    @patch('jarvis.tools.browser.is_safe_path')
    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_upload(self, mock_ensure, mock_is_safe):
        mock_is_safe.return_value = True
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        
        browser_module.browser_upload("#upload-btn", "/path/to/upload.txt")
        mock_page.set_input_files.assert_called_once_with("#upload-btn", "/path/to/upload.txt")

    @patch('jarvis.tools.browser.is_safe_path')
    @patch('jarvis.tools.browser._ensure_browser')
    def test_browser_upload_unsafe(self, mock_ensure, mock_is_safe):
        mock_is_safe.return_value = False
        mock_page = MagicMock()
        mock_ensure.return_value = mock_page
        
        with self.assertRaisesRegex(ValueError, "outside the allowed workspace"):
            browser_module.browser_upload("#upload-btn", "/unsafe/path.txt")
        
        mock_page.set_input_files.assert_not_called()
