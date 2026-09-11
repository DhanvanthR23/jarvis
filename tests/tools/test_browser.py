"""Tests for browser tools."""
import unittest

from jarvis.tools.browser import (
    browser_click,
    browser_download,
    browser_navigate,
    browser_read,
    browser_type,
    browser_upload,
)


class TestBrowser(unittest.TestCase):
    def test_browser_navigate(self):
        self.assertEqual(browser_navigate("https://example.com"), "Navigated to https://example.com")

    def test_browser_read(self):
        self.assertEqual(browser_read(), "Read content from page")
        self.assertEqual(browser_read(""), "Read content from page")
        self.assertEqual(browser_read(".content"), "Read content from selector .content")

    def test_browser_click(self):
        self.assertEqual(browser_click("#submit"), "Clicked element #submit")

    def test_browser_type(self):
        self.assertEqual(browser_type("#input", "hello"), "Typed 'hello' into element #input")

    def test_browser_download(self):
        self.assertEqual(browser_download("https://test.com/file", "/tmp/file"), "Downloaded https://test.com/file to /tmp/file")

    def test_browser_upload(self):
        self.assertEqual(browser_upload("#upload", "/tmp/file"), "Uploaded /tmp/file via #upload")
