"""Tests for Crash Recovery (G25.9)."""
import unittest

from jarvis.automation.authorization import AuthorizationStore
from jarvis.automation.models import AutomationJob, ScheduleTrigger, TriggerType
from jarvis.automation.recovery import CrashRecovery, RecoveryAction
from jarvis.automation.scheduler import ExecutionRecord, ExecutionStatus, JobStore


class TestCrashRecovery(unittest.TestCase):

    def _make_job(self, capability="network.status", **kwargs):
        defaults = {
            "name": "test",
            "capability": capability,
            "arguments": {},
            "trigger_type": TriggerType.SCHEDULE,
            "schedule": ScheduleTrigger(interval_seconds=1800),
        }
        defaults.update(kwargs)
        return AutomationJob(**defaults)

    def test_crash_recovery_does_not_unsafe_replay(self):
        """Mutation in STARTED state → SKIP, not retry."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(capability="service.restart")
        job_store.add(job)
        auth_store.create_authorization(job)

        record = ExecutionRecord(
            job_id=job.job_id, job_version=job.version,
            status=ExecutionStatus.STARTED,
        )

        recovery = CrashRecovery(job_store, auth_store)
        results = recovery.recover([record])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, RecoveryAction.SKIP)

    def test_safe_capability_retried_on_recovery(self):
        """Read-only job in STARTED state → RETRY."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(capability="network.status")
        job_store.add(job)
        auth_store.create_authorization(job)

        record = ExecutionRecord(
            job_id=job.job_id, job_version=job.version,
            status=ExecutionStatus.STARTED,
        )

        recovery = CrashRecovery(
            job_store, auth_store,
            safe_capabilities={"network.status"},
        )
        results = recovery.recover([record])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, RecoveryAction.RETRY)

    def test_missing_job_skipped(self):
        """Job deleted between crash and recovery → SKIP."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        record = ExecutionRecord(
            job_id="nonexistent", job_version=1,
            status=ExecutionStatus.STARTED,
        )

        recovery = CrashRecovery(job_store, auth_store)
        results = recovery.recover([record])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, RecoveryAction.SKIP)

    def test_expired_authorization_skipped(self):
        """Authorization expired between crash and recovery → SKIP."""
        import time
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(capability="network.status")
        job_store.add(job)
        auth_store.create_authorization(job, expires_at=time.time() - 1)

        record = ExecutionRecord(
            job_id=job.job_id, job_version=job.version,
            status=ExecutionStatus.STARTED,
        )

        recovery = CrashRecovery(
            job_store, auth_store,
            safe_capabilities={"network.status"},
        )
        results = recovery.recover([record])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, RecoveryAction.SKIP)

    def test_completed_records_ignored(self):
        """Already-completed records not touched by recovery."""
        job_store = JobStore()
        auth_store = AuthorizationStore()

        record = ExecutionRecord(
            job_id="x", job_version=1,
            status=ExecutionStatus.COMPLETED,
        )

        recovery = CrashRecovery(job_store, auth_store)
        results = recovery.recover([record])

        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main()
