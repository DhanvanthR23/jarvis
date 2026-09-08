"""Delegation handler and envelope validation (G26.5).

Provides the agent.delegate capability, validating targets and payloads.
"""
from typing import Any, Dict
from jarvis.orchestrator.roles import RoleValidator


class DelegationEnvelope:
    """Structured envelope for inter-agent delegation."""
    def __init__(self, target_role: str, task_description: str,
                 scoped_arguments: Dict[str, Any], timeout_seconds: int = 60):
        self.target_role = target_role
        self.task_description = task_description
        self.scoped_arguments = scoped_arguments
        self.timeout_seconds = timeout_seconds


class DelegationHandler:
    """Handles agent.delegate MCP tool calls."""
    
    def __init__(self, role_validator: RoleValidator, router):
        self.role_validator = role_validator
        self.router = router

    def handle_delegate(self, target_role: str, task_description: str,
                        scoped_arguments: Dict[str, Any] = None, timeout_seconds: int = 60) -> dict:
        """Process a delegation request from one agent to another."""
        if not self.role_validator.get_role(target_role):
            return {
                "status": "error",
                "message": f"Delegation failed: Unknown or disabled role '{target_role}'."
            }

        envelope = DelegationEnvelope(
            target_role=target_role,
            task_description=task_description,
            scoped_arguments=scoped_arguments or {},
            timeout_seconds=timeout_seconds,
        )

        try:
            # Route the delegation and get the result (blocking/turn-based)
            result = self.router.dispatch_delegation(envelope)
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "message": str(e)}
