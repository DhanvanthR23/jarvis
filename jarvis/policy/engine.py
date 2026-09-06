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
    def __init__(self, manifest: CapabilityManifest):
        self.manifest = manifest

    def check(self, tool_name: str, args: dict = None) -> PolicyResult:
        if tool_name not in self.manifest.capabilities:
            return PolicyResult(PolicyDecision.DENY, tool_name, "unknown capability")
        
        cap = self.manifest.capabilities[tool_name]
        if cap.risk_tier == RiskTier.SAFE:
            return PolicyResult(PolicyDecision.ALLOW, tool_name, "safe capability")
        elif cap.risk_tier == RiskTier.APPROVAL:
            return PolicyResult(PolicyDecision.APPROVE, tool_name, "requires approval")
        elif cap.risk_tier == RiskTier.DISABLED:
            return PolicyResult(PolicyDecision.DENY, tool_name, "capability disabled")
            
        return PolicyResult(PolicyDecision.DENY, tool_name, "invalid risk tier")
