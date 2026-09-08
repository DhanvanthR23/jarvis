"""Jarvis security invariants — codified from the threat model.

These are the non-negotiable rules the implementation must always preserve.
Every invariant has a unique ID, description, and violation response.
Security tests reference these IDs to ensure coverage.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict


class ViolationResponse(Enum):
    """What happens when an invariant is violated."""
    ARCHITECTURAL = auto()       # Enforced by design — no runtime check needed
    FAIL_CLOSED = auto()         # Operation refused, system stops
    DEFAULT_DENY = auto()        # Request denied, operation continues
    FREEZE_CAPABILITIES = auto() # No new capability work until fixed


@dataclass(frozen=True)
class SecurityInvariant:
    """A single non-negotiable security invariant."""
    id: str
    name: str
    description: str
    violation_response: ViolationResponse


# The canonical set of invariants from the threat model.
# Adding, removing, or modifying an invariant is itself a security-sensitive change.
INVARIANTS: Dict[str, SecurityInvariant] = {}

def _register(inv: SecurityInvariant) -> SecurityInvariant:
    INVARIANTS[inv.id] = inv
    return inv

INV_A = _register(SecurityInvariant(
    id="A",
    name="agy_untrusted",
    description="AGY is untrusted. Never assume the model or CLI will respect Jarvis's instructions.",
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_B = _register(SecurityInvariant(
    id="B",
    name="agy_never_unsandboxed",
    description="AGY never runs unsandboxed. There is no fallback to launching normal agy.",
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_C = _register(SecurityInvariant(
    id="C",
    name="sandbox_fail_closed",
    description=(
        "Sandbox failure is fail-closed. Missing bwrap, unavailable namespaces, "
        "failed mount setup, failed verification all mean AGY execution refused."
    ),
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_D = _register(SecurityInvariant(
    id="D",
    name="separate_defenses",
    description=(
        "OS containment and MCP policy are separate defenses. "
        "The sandbox protects the host from AGY. "
        "The policy engine protects capabilities from AGY. "
        "Neither replaces the other."
    ),
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_E = _register(SecurityInvariant(
    id="E",
    name="mcp_unix_socket",
    description=(
        "MCP is accessed through a Unix domain socket. "
        "No localhost TCP dependency. No IP networking for AGY."
    ),
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_F = _register(SecurityInvariant(
    id="F",
    name="manifest_integrity",
    description=(
        "capabilities.toml is integrity-verified at startup. "
        "Hash mismatch causes startup failure."
    ),
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_G = _register(SecurityInvariant(
    id="G",
    name="policy_checked",
    description=(
        "Every capability invocation is policy-checked: AGY → MCP → Policy → Tool. "
        "No tool directly trusts AGY."
    ),
    violation_response=ViolationResponse.DEFAULT_DENY,
))

INV_H = _register(SecurityInvariant(
    id="H",
    name="memory_is_capability",
    description="Memory writes don't bypass policy. Memory is a capability.",
    violation_response=ViolationResponse.DEFAULT_DENY,
))

INV_I = _register(SecurityInvariant(
    id="I",
    name="audit_outside_agy",
    description=(
        "AGY must have no access to audit.db, anchor.log, capabilities.toml, "
        "trusted manifest hash, or Jarvis credentials."
    ),
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_J = _register(SecurityInvariant(
    id="J",
    name="external_anchor",
    description=(
        "Audit chain has an external anchor. Hash chaining alone isn't enough. "
        "Latest audit hash is periodically written to a separate host-controlled "
        "append-only anchor."
    ),
    violation_response=ViolationResponse.FAIL_CLOSED,
))

INV_K = _register(SecurityInvariant(
    id="K",
    name="invariant_failure_freezes",
    description=(
        "If any security invariant fails, no new capability work proceeds "
        "until the failure is fixed and the relevant security tests pass."
    ),
    violation_response=ViolationResponse.FREEZE_CAPABILITIES,
))

# Expected invariant IDs — used by tests to detect accidental removal
EXPECTED_INVARIANT_IDS = frozenset(["A","B","C","D","E","F","G","H","I","J","K","AA","AB","AC","AD","AE","AF"])

# Threats that must each have a concrete control
EXPECTED_THREATS = frozenset({
    "agy_reads_secrets",
    "agy_accesses_host_filesystem",
    "agy_escapes_sandbox",
    "agy_bypasses_mcp",
    "policy_bug",
    "tool_bug",
    "memory_poisoning",
    "audit_tampering",
    "sandbox_regression",
})

INV_AA = _register(SecurityInvariant(
    id="AA",
    name="untrusted_agents",
    description="All agents are untrusted. No model tier or role carries intrinsic trust. Every agent runs in an isolated container.",
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_AB = _register(SecurityInvariant(
    id="AB",
    name="zero_direct_ipc",
    description="Zero direct agent-to-agent IPC. All data passing is mediated by the trusted Jarvis Controller.",
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_AC = _register(SecurityInvariant(
    id="AC",
    name="capability_compartmentalization",
    description="An agent cannot call or discover tools outside its explicitly assigned role in capabilities.toml.",
    violation_response=ViolationResponse.DEFAULT_DENY,
))

INV_AD = _register(SecurityInvariant(
    id="AD",
    name="no_transitive_authority",
    description="An agent cannot proxy its capabilities. Delegation inherits strict intersection of allowed capabilities.",
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_AE = _register(SecurityInvariant(
    id="AE",
    name="inter_agent_filtering",
    description="All text passed between agents must pass through the OutputSecurityFilter.",
    violation_response=ViolationResponse.ARCHITECTURAL,
))

INV_AF = _register(SecurityInvariant(
    id="AF",
    name="serialized_execution",
    description="Serialized execution & bounded concurrency. Cooperative turn-taking is enforced to prevent resource exhaustion.",
    violation_response=ViolationResponse.FAIL_CLOSED,
))
