"""Tests for Automation Policy (G25.6)."""
import time
import unittest
from jarvis.automation.models import AutomationJob, TriggerType, ScheduleTrigger, JobStatus
from jarvis.automation.authorization import AuthorizationStore
from jarvis.automation.policy import AutomationPolicy
from jarvis.policy.engine import PolicyEngine
from jarvis.policy.manifest import CapabilityManifest, Capability, RiskTier


class TestAutomationPolicy(unittest.TestCase):

    def _make_job(self, **kwargs):
        defaults = dict(
            name="wifi-check",
            capability="network_status",
            arguments={},
            trigger_type=TriggerType.SCHEDULE,
            schedule=ScheduleTrigger(interval_seconds=1800),
        )
        defaults.update(kwargs)
        return AutomationJob(**defaults)

    def _make_policy_engine(self, caps_dict):
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {
            name: Capability(name, tier) for name, tier in caps_dict.items()
        }
        manifest._loaded = True
        return PolicyEngine(manifest, active_role=None)

    def test_authorized_safe_job_allowed(self):
        auth_store = AuthorizationStore()
        policy_engine = self._make_policy_engine({"network_status": RiskTier.SAFE})
        policy = AutomationPolicy(auth_store, policy_engine)

        job = self._make_job()
        auth_store.create_authorization(job)

        result = policy.evaluate(job)
        self.assertTrue(result.allowed)

    def test_unauthorized_job_denied(self):
        auth_store = AuthorizationStore()
        policy = AutomationPolicy(auth_store)

        job = self._make_job()
        # No auth created

        result = policy.evaluate(job)
        self.assertFalse(result.allowed)
        self.assertIn("No valid authorization", result.reason)

    def test_disabled_capability_cannot_be_automated(self):
        auth_store = AuthorizationStore()
        policy_engine = self._make_policy_engine({"arbitrary_shell": RiskTier.DISABLED})
        policy = AutomationPolicy(auth_store, policy_engine)

        job = self._make_job(capability="arbitrary_shell")
        auth_store.create_authorization(job)

        result = policy.evaluate(job)
        self.assertFalse(result.allowed)
        self.assertIn("denied by policy", result.reason)

    def test_expired_authorization_denied(self):
        auth_store = AuthorizationStore()
        policy = AutomationPolicy(auth_store)

        job = self._make_job()
        auth_store.create_authorization(job, expires_at=time.time() - 1)

        result = policy.evaluate(job)
        self.assertFalse(result.allowed)

    def test_revoked_job_denied(self):
        auth_store = AuthorizationStore()
        policy = AutomationPolicy(auth_store)

        job = self._make_job(status=JobStatus.REVOKED)
        auth_store.create_authorization(job)

        result = policy.evaluate(job)
        self.assertFalse(result.allowed)
        self.assertIn("not runnable", result.reason)

    def test_automation_cannot_bypass_policy(self):
        """Automation goes through PolicyEngine — unknown caps denied."""
        auth_store = AuthorizationStore()
        policy_engine = self._make_policy_engine({"network_status": RiskTier.SAFE})
        policy = AutomationPolicy(auth_store, policy_engine)

        job = self._make_job(capability="unknown_tool")
        auth_store.create_authorization(job)

        result = policy.evaluate(job)
        self.assertFalse(result.allowed)

    def test_automation_cannot_call_arbitrary_shell(self):
        auth_store = AuthorizationStore()
        policy_engine = self._make_policy_engine({
            "arbitrary_shell": RiskTier.DISABLED,
            "sudo": RiskTier.DISABLED,
        })
        policy = AutomationPolicy(auth_store, policy_engine)

        for cap in ["arbitrary_shell", "sudo"]:
            job = self._make_job(capability=cap)
            auth_store.create_authorization(job)
            result = policy.evaluate(job)
            self.assertFalse(result.allowed, f"{cap} should be denied")


if __name__ == '__main__':
    unittest.main()
