"""Tests for Automation Output (G25.14)."""
import unittest
from unittest.mock import MagicMock

from jarvis.automation.authorization import AutomationAuthorization
from jarvis.automation.executor import AutomationExecutor
from jarvis.automation.models import AutomationJob
from jarvis.automation.scheduler import ExecutionRecord
from jarvis.output.filter import SAFE_REPLACEMENT, OutputSecurityFilter


class TestAutomationOutput(unittest.TestCase):

    def test_automation_output_uses_output_filter(self):
        controller = MagicMock()
        # Mock a tool returning a secret
        controller._execute_tool.return_value = {"data": "Your access key is AKIA1234567890123456."}

        output_filter = OutputSecurityFilter()
        executor = AutomationExecutor(controller, output_filter)

        job = AutomationJob(capability="test", arguments={})
        auth = AutomationAuthorization()
        record = ExecutionRecord()

        result = executor.execute(job, auth, record)

        # Original data is preserved, but filtered_output contains the redacted version
        self.assertIn("data", result)
        self.assertIn("filtered_output", result)
        self.assertEqual(result["filtered_output"], SAFE_REPLACEMENT)


if __name__ == '__main__':
    unittest.main()
