"""Approval System (G11).

Provides strictly bound, argument-verified approval caching for high-risk operations.
"""
import uuid
import time
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict

class ApprovalDecision(Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    DENY = "deny"

@dataclass
class ApprovalRequest:
    actor: str
    capability: str
    arguments: dict
    reason: str
    risk: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    @property
    def target(self) -> str:
        # Standardize target representation for legacy compatibility
        return str(self.arguments)

    def _compute_hash(self) -> str:
        """Compute a deterministic hash of the capability and its exact arguments."""
        # Sort keys to ensure deterministic JSON serialization
        arg_str = json.dumps(self.arguments, sort_keys=True)
        payload = f"{self.capability}:{arg_str}".encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

@dataclass
class ApprovalResponse:
    request_id: str
    decision: ApprovalDecision
    responded_at: float
    responded_by: str
    # If ALLOW_SESSION, it can expire
    expires_at: Optional[float] = None

class SessionApprovalCache:
    """Strictly caches approvals bound to EXACT capabilities and arguments."""
    def __init__(self):
        # Maps request hash to expires_at (float)
        self.active_approvals: Dict[str, float] = {}

    def is_approved(self, request: ApprovalRequest) -> bool:
        """Check if this exact request is currently approved for the session."""
        req_hash = request._compute_hash()
        if req_hash not in self.active_approvals:
            return False
            
        expires_at = self.active_approvals[req_hash]
        if time.time() > expires_at:
            # Expired
            del self.active_approvals[req_hash]
            return False
            
        return True

    def add_approval(self, request: ApprovalRequest, response: ApprovalResponse):
        """Record a session approval if granted."""
        if response.decision == ApprovalDecision.ALLOW_SESSION:
            req_hash = request._compute_hash()
            # Default to 1 hour expiration if not explicitly specified
            expires_at = response.expires_at if response.expires_at else time.time() + 3600
            self.active_approvals[req_hash] = expires_at

class ApprovalHandler:
    """Base class for handlers that solicit decisions from operators."""
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        raise NotImplementedError

class AutoDenyHandler(ApprovalHandler):
    """Always denies. Fail-safe."""
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(request.request_id, ApprovalDecision.DENY, time.time(), "auto")

class CLIApprovalHandler(ApprovalHandler):
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        print(f"\n--- APPROVAL REQUIRED ---")
        print(f"Actor: {request.actor}")
        print(f"Capability: {request.capability}")
        print(f"Arguments: {json.dumps(request.arguments, indent=2)}")
        print(f"Risk: {request.risk}")
        
        choice = input("Approve? (once/session/deny): ").strip().lower()
        decision = ApprovalDecision.DENY
        if choice == "once":
            decision = ApprovalDecision.ALLOW_ONCE
        elif choice == "session":
            decision = ApprovalDecision.ALLOW_SESSION
            
        return ApprovalResponse(request.request_id, decision, time.time(), "user")
