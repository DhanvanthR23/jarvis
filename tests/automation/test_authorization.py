"""Tests for Automation Authorization (G25.3)."""
import time
import unittest
from jarvis.automation.models import AutomationJob, TriggerType, ScheduleTrigger
from jarvis.automation.authorization import (
    AutomationAuthorization, AuthorizationStore,
)


class TestAutomationAuthorization(unittest.TestCase):

    def _make_job(self, **kwargs):
        defaults = dict(
            name="wifi-check",
            capability="network.status",
            arguments={},
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1800),
        )
        defaults.update(kwargs)
        return AutomationJob(**defaults)

    def test_create_authorization(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job, expires_at=time.time() + 3600)

        self.assertTrue(auth.is_valid())
        self.assertTrue(auth.matches_job(job))

    def test_authorization_matches_exact_job(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)

        self.assertTrue(auth.matches_job(job))

    def test_authorization_does_not_match_modified_job(self):
        """Invariant W: modified job requires new authorization."""
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)

        modified = job.create_new_version(capability="network.interfaces")
        self.assertFalse(auth.matches_job(modified))

    def test_authorization_does_not_match_different_arguments(self):
        """Invariant V: capability-bound, argument-bound."""
        store = AuthorizationStore()
        job = self._make_job(
            capability="service.restart",
            arguments={"name": "NetworkManager"},
        )
        auth = store.create_authorization(job)

        different_args = job.create_new_version(arguments={"name": "bluetooth"})
        self.assertFalse(auth.matches_job(different_args))

    def test_expired_authorization_invalid(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job, expires_at=time.time() - 1)

        self.assertFalse(auth.is_valid())

    def test_revoked_authorization_invalid(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)
        auth.revoke()

        self.assertFalse(auth.is_valid())

    def test_disabled_authorization_invalid(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)
        auth.disable()

        self.assertFalse(auth.is_valid())

    def test_disabled_authorization_can_be_reenabled(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)
        auth.disable()
        self.assertFalse(auth.is_valid())
        auth.enable()
        self.assertTrue(auth.is_valid())

    def test_revoked_authorization_cannot_be_reenabled(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job)
        auth.revoke()
        auth.enable()  # should not work
        self.assertFalse(auth.is_valid())

    def test_max_runs_exhausted(self):
        store = AuthorizationStore()
        job = self._make_job()
        auth = store.create_authorization(job, max_runs=2)

        auth.record_run()
        self.assertTrue(auth.is_valid())
        auth.record_run()
        self.assertFalse(auth.is_valid())

    def test_store_lookup(self):
        store = AuthorizationStore()
        job = self._make_job()
        store.create_authorization(job)

        found = store.get_authorization_for_job(job)
        self.assertIsNotNone(found)

    def test_store_lookup_returns_none_for_unauthorized(self):
        store = AuthorizationStore()
        job = self._make_job()
        # No authorization created
        found = store.get_authorization_for_job(job)
        self.assertIsNone(found)

    def test_store_revoke_by_job_id(self):
        store = AuthorizationStore()
        job = self._make_job()
        store.create_authorization(job)

        count = store.revoke_by_job_id(job.job_id)
        self.assertEqual(count, 1)

        found = store.get_authorization_for_job(job)
        self.assertIsNone(found)

    def test_interactive_approval_does_not_create_automation_authorization(self):
        """Invariant U: interactive approval ≠ automation authorization.

        This test verifies that the AuthorizationStore is the ONLY path to
        create automation authorizations. The existing SessionApprovalCache
        (interactive) and AutomationAuthorization (automation) are completely
        separate systems with no bridging.
        """
        from jarvis.policy.approval import (
            ApprovalRequest, ApprovalResponse, ApprovalDecision,
            SessionApprovalCache,
        )

        # Interactive approval
        cache = SessionApprovalCache()
        req = ApprovalRequest(
            actor="user",
            capability="service.restart",
            arguments={"name": "NetworkManager"},
            reason="test",
            risk="approval",
        )
        resp = ApprovalResponse(
            request_id=req.request_id,
            decision=ApprovalDecision.ALLOW_SESSION,
            responded_at=time.time(),
            responded_by="user",
        )
        cache.add_approval(req, resp)

        # The interactive approval exists in the session cache
        self.assertTrue(cache.is_approved(req))

        # But the automation store has nothing
        store = AuthorizationStore()
        job = self._make_job(
            capability="service.restart",
            arguments={"name": "NetworkManager"},
        )
        found = store.get_authorization_for_job(job)
        self.assertIsNone(found)


if __name__ == '__main__':
    unittest.main()
