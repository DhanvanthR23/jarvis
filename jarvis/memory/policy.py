from dataclasses import dataclass

from .store import MemoryEntry, MemoryStore


@dataclass
class MemoryWriteRequest:
    entry: MemoryEntry
    source_type: str

class MemoryPolicyEngine:
    def __init__(self, memory_store: MemoryStore, approval_handler = None):
        self.memory_store = memory_store
        self.approval_handler = approval_handler

    def process_write(self, request: MemoryWriteRequest) -> bool:
        if request.source_type == 'user_explicit':
            self.memory_store.write(request.entry)
            return True
        elif request.source_type == 'agent_inferred':
            request.entry.confidence = 'pending'
            self.memory_store.write(request.entry)
            return True
        elif request.source_type == 'agent_high_impact':
            if self.approval_handler:

                from jarvis.policy.approval import ApprovalRequest
                approval_req = ApprovalRequest(
                    actor='agent',
                    capability='memory_write',
                    arguments={'key': request.entry.key, 'value': request.entry.value},
                    reason='High impact memory write',
                    risk='approval',
                )
                decision = self.approval_handler.request_approval(approval_req)
                if decision and decision.decision.name.startswith("ALLOW"):
                    self.memory_store.write(request.entry)
                    return True
            return False
        return False

    def review_pending(self) -> list:
        return self.memory_store.list_pending()

    def approve_pending(self, key: str) -> bool:
        entry = self.memory_store.read(key)
        if entry and entry.confidence == 'pending':
            entry.confidence = 'explicit'
            self.memory_store.write(entry)
            return True
        return False

    def reject_pending(self, key: str) -> bool:
        return self.memory_store.delete(key)
