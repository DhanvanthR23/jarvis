"""Tests for Revocation and Expiration (G25.10)."""
import time
import unittest
from jarvis.automation.models import AutomationJob, TriggerType, ScheduleTrigger, JobStatus
from jarvis.automation.authorization import AuthorizationStore
from jarvis.automation.scheduler import AutomationScheduler, JobStore


class TestRevocationExpiration(unittest.TestCase):

    def _make_job(self, **kwargs):
        defaults = dict(
            name="test",
            capability="network.status",
            arguments={},
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1800),
        )
        defaults.update(kwargs)
        return AutomationJob(**defaults)

    def test_expired_automation_cannot_execute(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(expires_at=time.time() - 1)
        job_store.add(job)
        auth_store.create_authorization(job)

        executed = []
        scheduler = AutomationScheduler(job_store, auth_store, lambda j, a, r: executed.append(1))
        scheduler.trigger_manual(job.job_id)
        self.assertEqual(len(executed), 0)

    def test_revoked_automation_cannot_execute(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        job_store.add(job)
        auth = auth_store.create_authorization(job)
        auth.revoke()

        executed = []
        scheduler = AutomationScheduler(job_store, auth_store, lambda j, a, r: executed.append(1))
        scheduler.trigger_manual(job.job_id)
        self.assertEqual(len(executed), 0)

    def test_revoke_by_job_id_blocks_all_versions(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job()
        auth_store.create_authorization(job)
        job2 = job.create_new_version()
        auth_store.create_authorization(job2)

        count = auth_store.revoke_by_job_id(job.job_id)
        self.assertEqual(count, 2)

        self.assertIsNone(auth_store.get_authorization_for_job(job))
        self.assertIsNone(auth_store.get_authorization_for_job(job2))

    def test_disabled_job_does_not_execute(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(status=JobStatus.DISABLED)
        job_store.add(job)
        auth_store.create_authorization(job)

        executed = []
        scheduler = AutomationScheduler(job_store, auth_store, lambda j, a, r: executed.append(1))
        scheduler.trigger_manual(job.job_id)
        self.assertEqual(len(executed), 0)

    def test_expired_authorization_blocks_even_if_job_valid(self):
        job_store = JobStore()
        auth_store = AuthorizationStore()

        job = self._make_job(expires_at=time.time() + 3600)  # job valid
        job_store.add(job)
        auth_store.create_authorization(job, expires_at=time.time() - 1)  # auth expired

        executed = []
        scheduler = AutomationScheduler(job_store, auth_store, lambda j, a, r: executed.append(1))
        scheduler.trigger_manual(job.job_id)
        self.assertEqual(len(executed), 0)


if __name__ == '__main__':
    unittest.main()
