import uuid
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod

class ApprovalDecision(Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    DENY = "deny"

@dataclass
class ApprovalRequest:
    actor: str
    capability: str
    target: str
    arguments: dict
    reason: str
    risk: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    expiration: Optional[float] = None

@dataclass
class ApprovalResponse:
    request_id: str
    decision: ApprovalDecision
    responded_at: float
    responded_by: str

class ApprovalHandler(ABC):
    @abstractmethod
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        pass

class AutoDenyHandler(ApprovalHandler):
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(request.request_id, ApprovalDecision.DENY, time.time(), "auto")

class CLIApprovalHandler(ApprovalHandler):
    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        print(f"\n--- APPROVAL REQUIRED ---")
        print(f"Actor: {request.actor}")
        print(f"Capability: {request.capability}")
        print(f"Target: {request.target}")
        print(f"Risk: {request.risk}")
        print(f"Arguments: {request.arguments}")
        
        choice = input("Approve? (once/session/deny): ").strip().lower()
        decision = ApprovalDecision.DENY
        if choice == "once":
            decision = ApprovalDecision.ALLOW_ONCE
        elif choice == "session":
            decision = ApprovalDecision.ALLOW_SESSION
            
        return ApprovalResponse(request.request_id, decision, time.time(), "user")

class SessionApprovalCache:
    def __init__(self):
        self.approvals = {}

    def is_approved(self, capability: str) -> bool:
        return self.approvals.get(capability, False)

    def add_approval(self, capability: str, decision: ApprovalDecision):
        if decision == ApprovalDecision.ALLOW_SESSION:
            self.approvals[capability] = True
