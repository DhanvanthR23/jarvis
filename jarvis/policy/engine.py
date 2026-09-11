from enum import Enum
from dataclasses import dataclass
from .manifest import CapabilityManifest, RiskTier

class PolicyDecision(Enum):
    ALLOW = "allow"
    APPROVE = "approve"
    DENY = "deny"

@dataclass
class PolicyResult:
    decision: PolicyDecision
    capability: str
    reason: str

class PolicyEngine:
    def __init__(self, manifest: CapabilityManifest, active_role: str = "system_diagnostics"):
        self.manifest = manifest
        self.active_role = active_role

    def check(self, tool_name: str, args: dict = None) -> PolicyResult:
        if tool_name not in self.manifest.capabilities:
            return PolicyResult(PolicyDecision.DENY, tool_name, "unknown capability")
        
        cap = self.manifest.capabilities[tool_name]
        
        # Enforce role limits
        if self.active_role:
            if self.active_role not in self.manifest.roles:
                return PolicyResult(PolicyDecision.DENY, tool_name, f"role {self.active_role} not found in manifest")
            
            role = self.manifest.roles[self.active_role]
            if tool_name not in role.allowed_capabilities:
                return PolicyResult(PolicyDecision.DENY, tool_name, f"capability not allowed for role {self.active_role}")
            
            if cap.risk_tier == RiskTier.APPROVAL and not role.can_mutate:
                return PolicyResult(PolicyDecision.DENY, tool_name, f"role {self.active_role} is not permitted to mutate state")

        if cap.risk_tier == RiskTier.SAFE:
            return PolicyResult(PolicyDecision.ALLOW, tool_name, "safe capability")
        elif cap.risk_tier == RiskTier.APPROVAL:
            return PolicyResult(PolicyDecision.APPROVE, tool_name, "requires approval")
        elif cap.risk_tier == RiskTier.DISABLED:
            return PolicyResult(PolicyDecision.DENY, tool_name, "capability disabled")
            
        return PolicyResult(PolicyDecision.DENY, tool_name, "invalid risk tier")
