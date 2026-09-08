"""AGY constrained automation (G25.13).

When AGY reasons inside an automation job, it is constrained to the
job's authorized capability set. The prompt makes scope explicit,
but the Policy Engine is the actual enforcement mechanism.
"""
from typing import List, Optional
from jarvis.automation.models import AutomationJob


class AutomationPromptBuilder:
    """Builds a scope-constrained prompt for AGY within automation context.

    The prompt is NOT the security control — PolicyEngine is.
    The prompt exists to reduce wasted AGY reasoning cycles on
    capabilities that will be denied anyway.
    """

    def build(self, job: AutomationJob) -> str:
        """Build a constrained AGY prompt for the given job."""
        return (
            f"You are executing automation job {job.name}:{job.job_id[:8]} (v{job.version}).\n"
            f"\n"
            f"Authorized capability:\n"
            f"  {job.capability}\n"
            f"\n"
            f"Authorized arguments:\n"
            f"  {job.arguments}\n"
            f"\n"
            f"Do not request or invoke capabilities outside the authorized job.\n"
            f"Any unauthorized capability request will be denied by Policy."
        )


class AGYScopeEnforcer:
    """Validates that AGY's tool calls stay within job scope.

    This is a defense-in-depth check applied before the tool call
    reaches PolicyEngine. PolicyEngine remains the authoritative control.
    """

    def is_within_scope(self, job: AutomationJob, tool_name: str, args: dict) -> bool:
        """Check if a tool call is within the job's authorized scope."""
        if tool_name != job.capability:
            return False
        if args != job.arguments:
            return False
        return True

    def filter_calls(self, job: AutomationJob,
                     tool_calls: List[dict]) -> tuple:
        """Split tool calls into allowed and denied lists.

        Returns (allowed, denied) where each is a list of tool call dicts.
        """
        allowed = []
        denied = []
        for call in tool_calls:
            if self.is_within_scope(job, call.get("tool"), call.get("args", {})):
                allowed.append(call)
            else:
                denied.append(call)
        return allowed, denied
