"""Tests for Automation Audit integration (G25.11)."""
import unittest
from unittest.mock import MagicMock
from jarvis.automation.executor import AutomationExecutor
from jarvis.automation.models import AutomationJob
from jarvis.automation.authorization import AutomationAuthorization
from jarvis.automation.scheduler import ExecutionRecord


class TestAutomationAudit(unittest.TestCase):

    def test_automation_audit_failure_fails_closed(self):
        controller = MagicMock()
        # Simulate the controller raising an exception because the audit logger failed
        controller._execute_tool.side_effect = RuntimeError("Audit failure: DB disconnected")

        executor = AutomationExecutor(controller)

        job = AutomationJob(capability="network.status")
        auth = AutomationAuthorization()
        record = ExecutionRecord()

        with self.assertRaises(RuntimeError) as ctx:
            executor.execute(job, auth, record)
        
        self.assertIn("Audit failure", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
