"""Tests for AGY Constrained Automation (G25.13)."""
import unittest
from jarvis.automation.models import AutomationJob
from jarvis.automation.agy_scope import AutomationPromptBuilder, AGYScopeEnforcer


class TestAGYScope(unittest.TestCase):

    def _make_job(self):
        return AutomationJob(
            name="test-job",
            capability="network.status",
            arguments={"interface": "wlan0"},
        )

    def test_prompt_builder_includes_scope(self):
        builder = AutomationPromptBuilder()
        job = self._make_job()
        prompt = builder.build(job)

        self.assertIn(job.name, prompt)
        self.assertIn("network.status", prompt)
        self.assertIn("wlan0", prompt)

    def test_scope_enforcer_allows_exact_match(self):
        enforcer = AGYScopeEnforcer()
        job = self._make_job()

        self.assertTrue(enforcer.is_within_scope(job, "network.status", {"interface": "wlan0"}))

    def test_scope_enforcer_denies_different_capability(self):
        enforcer = AGYScopeEnforcer()
        job = self._make_job()

        self.assertFalse(enforcer.is_within_scope(job, "service.restart", {"interface": "wlan0"}))

    def test_scope_enforcer_denies_different_arguments(self):
        enforcer = AGYScopeEnforcer()
        job = self._make_job()

        self.assertFalse(enforcer.is_within_scope(job, "network.status", {"interface": "eth0"}))

    def test_filter_calls_splits_correctly(self):
        enforcer = AGYScopeEnforcer()
        job = self._make_job()

        calls = [
            {"tool": "network.status", "args": {"interface": "wlan0"}},  # Allowed
            {"tool": "network.status", "args": {"interface": "eth0"}},   # Denied (wrong args)
            {"tool": "arbitrary_shell", "args": {"cmd": "ls"}},          # Denied (wrong cap)
        ]

        allowed, denied = enforcer.filter_calls(job, calls)
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(denied), 2)
        self.assertEqual(allowed[0]["tool"], "network.status")


if __name__ == '__main__':
    unittest.main()
