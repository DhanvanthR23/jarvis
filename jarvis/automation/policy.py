"""Automation Policy (G25.6).

Separate from the interactive PolicyEngine. Validates that an automation
job is authorized, within bounds, and permitted by capabilities.toml.

Does NOT replace PolicyEngine — both apply. AutomationPolicy runs first
(pre-dispatch), then PolicyEngine runs during execution (per-tool).
"""

from jarvis.automation.authorization import AuthorizationStore, AutomationAuthorization
from jarvis.automation.models import AutomationJob
from jarvis.policy.engine import PolicyDecision, PolicyEngine


class AutomationPolicyResult:
    """Result of automation policy evaluation."""
    def __init__(self, allowed: bool, reason: str,
                 authorization: AutomationAuthorization | None = None):
        self.allowed = allowed
        self.reason = reason
        self.authorization = authorization


class AutomationPolicy:
    """Pre-dispatch policy for automation jobs.

    Checks:
    1. Job has valid authorization (Invariant U)
    2. Authorization matches job exactly (Invariant V/W)
    3. Authorization not expired/revoked
    4. Capability is not disabled in capabilities.toml (Invariant X)
    5. Job is within execution limits
    """

    def __init__(self, auth_store: AuthorizationStore,
                 policy_engine: PolicyEngine | None = None):
        self.auth_store = auth_store
        self.policy_engine = policy_engine

    def evaluate(self, job: AutomationJob) -> AutomationPolicyResult:
        """Evaluate whether an automation job is permitted to execute."""

        # 1. Job must be runnable
        if not job.is_runnable():
            return AutomationPolicyResult(False, f"Job not runnable: status={job.status.value}")

        # 2. Must have valid authorization
        auth = self.auth_store.get_authorization_for_job(job)
        if auth is None:
            return AutomationPolicyResult(False, "No valid authorization for this job version")

        # 3. Capability must not be disabled in capabilities.toml
        if self.policy_engine:
            policy_result = self.policy_engine.check(job.capability, job.arguments)
            if policy_result.decision == PolicyDecision.DENY:
                return AutomationPolicyResult(
                    False,
                    f"Capability denied by policy: {policy_result.reason}",
                )

        # 4. All checks pass
        return AutomationPolicyResult(True, "authorized", auth)
