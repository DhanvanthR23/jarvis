"""Tests for Automation Job Model (G25.2)."""
import time
import unittest
from jarvis.automation.models import (
    AutomationJob, JobStatus, TriggerType, ConcurrencyPolicy,
    ScheduleTrigger, EventTrigger,
)


class TestAutomationJob(unittest.TestCase):

    def test_job_creation(self):
        job = AutomationJob(
            name="wifi-check",
            capability="network.status",
            arguments={},
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1800),
        )
        self.assertEqual(job.name, "wifi-check")
        self.assertEqual(job.capability, "network.status")
        self.assertEqual(job.version, 1)
        self.assertTrue(job.is_runnable())

    def test_job_hash_deterministic(self):
        job = AutomationJob(
            name="wifi-check",
            capability="network.status",
            arguments={"interface": "wlan0"},
            trigger_type=TriggerType.SCHEDULE,
        )
        h1 = job.compute_hash()
        h2 = job.compute_hash()
        self.assertEqual(h1, h2)

    def test_job_hash_changes_on_capability_change(self):
        job = AutomationJob(
            name="wifi-check",
            capability="network.status",
            arguments={},
        )
        h1 = job.compute_hash()

        job2 = job.create_new_version(capability="network.interfaces")
        h2 = job2.compute_hash()
        self.assertNotEqual(h1, h2)

    def test_job_hash_changes_on_argument_change(self):
        job = AutomationJob(
            name="restart-nm",
            capability="service.restart",
            arguments={"name": "NetworkManager"},
        )
        h1 = job.compute_hash()

        job2 = job.create_new_version(arguments={"name": "bluetooth"})
        h2 = job2.compute_hash()
        self.assertNotEqual(h1, h2)

    def test_new_version_bumps_version_number(self):
        job = AutomationJob(name="test", capability="x", version=1)
        job2 = job.create_new_version(capability="y")
        self.assertEqual(job2.version, 2)
        self.assertEqual(job2.job_id, job.job_id)

    def test_new_version_resets_run_count(self):
        job = AutomationJob(name="test", capability="x")
        job.run_count = 5
        job2 = job.create_new_version()
        self.assertEqual(job2.run_count, 0)

    def test_expired_job_not_runnable(self):
        job = AutomationJob(
            name="test",
            capability="x",
            expires_at=time.time() - 1,  # already expired
        )
        self.assertFalse(job.is_runnable())

    def test_disabled_job_not_runnable(self):
        job = AutomationJob(name="test", capability="x", status=JobStatus.DISABLED)
        self.assertFalse(job.is_runnable())

    def test_revoked_job_not_runnable(self):
        job = AutomationJob(name="test", capability="x", status=JobStatus.REVOKED)
        self.assertFalse(job.is_runnable())

    def test_max_runs_exhausted_not_runnable(self):
        job = AutomationJob(name="test", capability="x", max_runs=3, run_count=3)
        self.assertFalse(job.is_runnable())

    def test_record_run_increments(self):
        job = AutomationJob(name="test", capability="x")
        self.assertEqual(job.run_count, 0)
        job.record_run()
        self.assertEqual(job.run_count, 1)


class TestJobIntegrity(unittest.TestCase):
    """Tests that job versioning enforces re-authorization on changes."""

    def test_modified_job_has_different_hash(self):
        job = AutomationJob(
            name="restart-nm",
            capability="service.restart",
            arguments={"name": "NetworkManager"},
        )
        original_hash = job.compute_hash()

        modified = job.create_new_version(arguments={"name": "bluetooth"})
        self.assertNotEqual(modified.compute_hash(), original_hash)

    def test_modified_trigger_changes_hash(self):
        job = AutomationJob(
            name="test",
            capability="x",
            trigger_type=TriggerType.SCHEDULE,
        )
        h1 = job.compute_hash()

        job2 = job.create_new_version(trigger_type=TriggerType.EVENT)
        self.assertNotEqual(job2.compute_hash(), h1)


if __name__ == '__main__':
    unittest.main()
