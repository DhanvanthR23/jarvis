import hashlib

def compute_event_hash(event_data: str, previous_hash: str = '') -> str:
    return hashlib.sha256((previous_hash + event_data).encode("utf-8")).hexdigest()

class AuditChain:
    def __init__(self):
        self._current_hash = ""

    @property
    def current_hash(self) -> str:
        return self._current_hash

    def add_event(self, event_data: str) -> str:
        self._current_hash = compute_event_hash(event_data, self._current_hash)
        return self._current_hash

    def verify_chain(self, events: list, expected_hashes: list) -> bool:
        if len(events) != len(expected_hashes):
            return False
        curr = ""
        for i, ev in enumerate(events):
            curr = compute_event_hash(ev, curr)
            if curr != expected_hashes[i]:
                return False
        return True
