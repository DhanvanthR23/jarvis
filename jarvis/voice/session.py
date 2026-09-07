"""Voice session tracking (plan2.md invariant N).

Tracks pending approvals with request-binding, freshness, single-use,
and 3-attempt retry limit per invariants N and O.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class VoicePendingApproval:
    """A pending voice approval — request-bound, fresh, single-use."""
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ''
    capability: str = ''
    arguments: dict = field(default_factory=dict)
    argument_hash: str = ''
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0           # absolute timestamp
    consumed: bool = False
    failed_attempts: int = 0
    denied: bool = False

    MAX_ATTEMPTS = 3
    DEFAULT_TTL = 60.0  # seconds

    def __post_init__(self):
        if not self.argument_hash:
            self.argument_hash = self._compute_hash()
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + self.DEFAULT_TTL

    def _compute_hash(self) -> str:
        canonical = json.dumps(
            {'capability': self.capability, 'arguments': self.arguments},
            sort_keys=True
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        """Approval is valid iff not consumed, not denied, not expired."""
        return not self.consumed and not self.denied and not self.is_expired()

    def record_failed_attempt(self) -> None:
        """Record failed confirmation. After MAX_ATTEMPTS, deny outright."""
        self.failed_attempts += 1
        if self.failed_attempts >= self.MAX_ATTEMPTS:
            self.denied = True

    def consume(self) -> None:
        """Mark as consumed — single-use, immediate invalidation."""
        self.consumed = True


class VoiceSession:
    """Tracks voice approvals for one session. Enforces invariants N, O."""

    def __init__(self, session_id: str = ''):
        self.session_id = session_id or str(uuid.uuid4())
        self._pending: Dict[str, VoicePendingApproval] = {}

    def create_approval(self, capability: str, arguments: dict) -> VoicePendingApproval:
        """Create a new pending approval bound to this session."""
        approval = VoicePendingApproval(
            session_id=self.session_id,
            capability=capability,
            arguments=arguments,
        )
        self._pending[approval.approval_id] = approval
        return approval

    def get_pending(self, approval_id: str) -> Optional[VoicePendingApproval]:
        """Retrieve a pending approval by ID. Returns None if not found."""
        return self._pending.get(approval_id)

    def get_all_pending(self) -> list:
        """Return all currently valid (non-consumed, non-denied, non-expired) approvals."""
        return [a for a in self._pending.values() if a.is_valid()]

    def resolve_confirmation(self, approval_id: str) -> Optional[VoicePendingApproval]:
        """Attempt to resolve a confirmation to exactly one pending approval.

        Returns the approval if valid; None otherwise.
        Does NOT consume — caller must call consume() after validation passes.
        """
        approval = self._pending.get(approval_id)
        if approval is None:
            return None
        if not approval.is_valid():
            return None
        return approval

    def cleanup_expired(self) -> int:
        """Remove expired/consumed/denied approvals. Returns count removed."""
        to_remove = [
            aid for aid, a in self._pending.items()
            if a.consumed or a.denied or a.is_expired()
        ]
        for aid in to_remove:
            del self._pending[aid]
        return len(to_remove)
