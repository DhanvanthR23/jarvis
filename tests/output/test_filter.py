"""Tests for OutputSecurityFilter (G24.11 & G24.12)."""
import unittest
from jarvis.output.filter import OutputSecurityFilter, SAFE_REPLACEMENT
from jarvis.output.sensitivity import SensitivityTag, SensitivityLevel

class TestOutputSecurityFilter(unittest.TestCase):
    def setUp(self):
        self.filter = OutputSecurityFilter()

    def test_filter_cannot_be_disabled(self):
        with self.assertRaises(RuntimeError):
            OutputSecurityFilter(enabled=False)

    def test_filter_tagged_safe(self):
        tags = [SensitivityTag(SensitivityLevel.PUBLIC, "test")]
        self.assertEqual(self.filter.filter("safe text", tags), "safe text")

    def test_filter_tagged_secret(self):
        tags = [SensitivityTag(SensitivityLevel.SECRET, "test")]
        self.assertEqual(self.filter.filter("safe text", tags), SAFE_REPLACEMENT)

    def test_filter_patterns_no_secrets(self):
        self.assertEqual(self.filter.filter("This is a normal sentence."), "This is a normal sentence.")

    def test_filter_patterns_api_key(self):
        text = "I found the key: sk-abcdefghijklmnopqrstuvwxyz"
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)

    def test_filter_patterns_aws_key(self):
        text = "Your access key is AKIA1234567890123456."
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)

    def test_filter_patterns_private_key(self):
        text = "Here is the key:\n-----BEGIN RSA PRIVATE KEY-----\n..."
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)

    def test_filter_patterns_password(self):
        text = "The config is password: supersecretpassword123"
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)

    def test_no_partial_redaction(self):
        # A partial redaction would look like "The config is password: [REDACTED]"
        # We ensure it hard fails over to the SAFE_REPLACEMENT string entirely.
        text = "I found the password=secret123 in the file."
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)


    def test_filter_patterns_reformatted_secret(self):
        # A slightly reformatted literal substring (e.g. spaced out)
        text = "The key is A K I A 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6"
        self.assertEqual(self.filter.filter(text), SAFE_REPLACEMENT)

if __name__ == '__main__':
    unittest.main()
