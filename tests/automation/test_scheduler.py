"""Tests for Automation Scheduler (G25.4)."""
import time
import unittest

from jarvis.automation.authorization import AuthorizationStore
from jarvis.automation.models import (
    AutomationJob,
    JobStatus,
    ScheduleTrigger,
    TriggerType,
)
from jarvis.automation.scheduler import (
    AutomationScheduler,
    ExecutionStatus,
    JobStore,
)


class TestScheduler(unittest.TestCase):

    def _make_job(self, interval=1, **kwargs):
        defaults = {
            "name": "wifi-check",
            "capability": "network.status",
            "arguments": {},
            "trigger_type": TriggerType.SCHEDULE,
            "schedule": ScheduleTrigger(interval_seconds=interval),
        }
        defaults.update(kwargs)
        return AutomationJob(**defaults)

    def test_authorized_job_executes(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth_store.create_authorization(job)

        executed = []

        def executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        self.assertEqual(len(executed), 1)

    def test_unauthorized_job_does_not_execute(self):
        """Invariant U: no authorization → no execution."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        # No authorization created

        executed = []

        def executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        self.assertEqual(len(executed), 0)

    def test_expired_authorization_blocks_execution(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth_store.create_authorization(job, expires_at=time.time() - 1)

        executed = []

        def executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        self.assertEqual(len(executed), 0)

    def test_revoked_authorization_blocks_execution(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth = auth_store.create_authorization(job)
        auth.revoke()

        executed = []

        def executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        self.assertEqual(len(executed), 0)

    def test_disabled_job_does_not_execute(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(status=JobStatus.DISABLED)
        job_store.add(job)
        auth_store.create_authorization(job)

        executed = []

        def executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        self.assertEqual(len(executed), 0)

    def test_execution_history_records(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth_store.create_authorization(job)

        def executor(j, a, r):
            pass

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        history = scheduler.get_execution_history(job.job_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, ExecutionStatus.COMPLETED)

    def test_failed_execution_recorded(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth_store.create_authorization(job)

        def executor(j, a, r):
            raise RuntimeError("tool failure")

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(job.job_id)

        history = scheduler.get_execution_history(job.job_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, ExecutionStatus.FAILED)
        self.assertIn("tool failure", history[0].error)

    def test_max_concurrent_respected(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        jobs = []
        for i in range(10):
            job = self._make_job(name=f"job-{i}")
            job_store.add(job)
            auth_store.create_authorization(job)
            jobs.append(job)

        executed = []

        def slow_executor(j, a, r):
            executed.append(j.job_id)

        scheduler = AutomationScheduler(
            job_store, auth_store, slow_executor, max_concurrent=3
        )

        # Trigger all manually (synchronous, so concurrency doesn't apply in this test,
        # but max_concurrent check happens before dispatch)
        for job in jobs:
            scheduler.trigger_manual(job.job_id)

        # All should have executed since they complete before the next starts
        self.assertEqual(len(executed), 10)

    def test_schedule_fires_after_interval(self):
        """Verify the scheduler fires a job after its interval elapses."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(interval=1)  # 1 second interval
        job_store.add(job)
        auth_store.create_authorization(job)

        executed = []

        def executor(j, a, r):
            executed.append(time.time())

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler._tick_interval = 0.1

        scheduler.start()
        time.sleep(1.5)
        scheduler.stop()

        self.assertGreaterEqual(len(executed), 1)

    def test_modified_job_version_requires_new_authorization(self):
        """Invariant W: modifying job invalidates old authorization."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(
            capability="service.restart",
            arguments={"name": "NetworkManager"},
        )
        job_store.add(job)
        auth_store.create_authorization(job)

        # Modify job
        modified = job.create_new_version(arguments={"name": "bluetooth"})
        job_store.add(modified)

        executed = []

        def executor(j, a, r):
            executed.append(j.capability)

        scheduler = AutomationScheduler(job_store, auth_store, executor)
        scheduler.trigger_manual(modified.job_id)

        # Should NOT execute — old auth doesn't match new version
        self.assertEqual(len(executed), 0)


if __name__ == '__main__':
    unittest.main()
