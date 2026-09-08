"""Full Automation E2E (G25.16).

Tests the complete flow:
Scheduler Tick → Job → Auth Verify → Policy Verify → Controller → Tool → Output
"""
import time
import unittest
from jarvis.automation.models import AutomationJob, TriggerType, ScheduleTrigger
from jarvis.automation.authorization import AuthorizationStore
from jarvis.automation.scheduler import AutomationScheduler, JobStore, ExecutionStatus
from jarvis.automation.policy import AutomationPolicy
from jarvis.automation.executor import AutomationExecutor
from jarvis.policy.engine import PolicyEngine
from jarvis.policy.manifest import CapabilityManifest, Capability, RiskTier
from jarvis.core.controller import JarvisController


class MockAgent:
    def __init__(self):
        self.session_id = "test-session"


class MockAuditLogger:
    def log_event(self, **kwargs):
        pass


class TestAutomationE2E(unittest.TestCase):

    def test_full_schedule_execution_pipeline(self):
        """E2E test: a scheduled job executes successfully and is filtered."""
        # 1. Setup policy
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {
            "network.status": Capability("network.status", RiskTier.SAFE)
        }
        manifest._loaded = True
        policy_engine = PolicyEngine(manifest)

        # 2. Setup controller with mocked tool registry
        tool_registry = {
            "network.status": {
                "handler": lambda **kwargs: "Network is up. AKIA1234567890123456"
            }
        }
        controller = JarvisController(
            agent_backend=MockAgent(),
            policy_engine=policy_engine,
            audit_logger=MockAuditLogger(),
            tool_registry=tool_registry,
        )

        # 3. Setup automation infrastructure
        job_store = JobStore()
        auth_store = AuthorizationStore()
        auto_policy = AutomationPolicy(auth_store, policy_engine)
        executor = AutomationExecutor(controller)

        # 4. Create job and authorization
        job = AutomationJob(
            name="check-net",
            capability="network.status",
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1),
        )
        job_store.add(job)
        auth_store.create_authorization(job)

        # Execution collector for the test
        executed_results = []
        def _execute_callback(j, a, r):
            result = executor.execute(j, a, r)
            executed_results.append(result)

        scheduler = AutomationScheduler(
            job_store, auth_store, _execute_callback,
            policy_check=lambda j: auto_policy.evaluate(j).allowed
        )
        scheduler._tick_interval = 0.1

        # 5. Run scheduler
        scheduler.start()
        time.sleep(1.5)  # Let it tick and fire the 1-second interval job
        scheduler.stop()

        # 6. Verify assertions
        history = scheduler.get_execution_history(job.job_id)
        self.assertGreaterEqual(len(history), 1)
        
        record = history[0]
        print("Error:", record.error)
        self.assertEqual(record.status, ExecutionStatus.COMPLETED)
        
        # Verify tool result passed through the executor correctly
        self.assertGreaterEqual(len(executed_results), 1)
        res = executed_results[0]
        self.assertEqual(res["status"], "success")
        
        # Verify OutputSecurityFilter applied in executor
        self.assertIn("filtered_output", res)
        self.assertNotIn("AKIA1234567890123456", res["filtered_output"])
        from jarvis.output.filter import SAFE_REPLACEMENT
        self.assertIn(SAFE_REPLACEMENT, res["filtered_output"])

    def test_e2e_denied_by_policy(self):
        """E2E test: job fails if capability is disabled in capabilities.toml."""
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {
            "arbitrary_shell": Capability("arbitrary_shell", RiskTier.DISABLED)
        }
        manifest._loaded = True
        policy_engine = PolicyEngine(manifest)

        controller = JarvisController(
            agent_backend=MockAgent(),
            policy_engine=policy_engine,
        )

        job_store = JobStore()
        auth_store = AuthorizationStore()
        auto_policy = AutomationPolicy(auth_store, policy_engine)
        executor = AutomationExecutor(controller)

        job = AutomationJob(
            name="bad-job",
            capability="arbitrary_shell",
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1),
        )
        job_store.add(job)
        auth_store.create_authorization(job)

        executed_results = []
        def _execute_callback(j, a, r):
            result = executor.execute(j, a, r)
            executed_results.append(result)

        scheduler = AutomationScheduler(
            job_store, auth_store, _execute_callback,
            policy_check=lambda j: auto_policy.evaluate(j).allowed
        )

        scheduler.trigger_manual(job.job_id)

        # The policy_check in dispatch blocks it before executor is called
        self.assertEqual(len(executed_results), 0)
        history = scheduler.get_execution_history()
        self.assertEqual(len(history), 0)


if __name__ == '__main__':
    unittest.main()
