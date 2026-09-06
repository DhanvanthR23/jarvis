import json
import hashlib
import time
from .database import AuditDatabase, AuditRecord
from .chain import AuditChain
from .anchor import AuditAnchor

class AuditLogger:
    def __init__(self, db_path: str, anchor_path: str):
        self.db = AuditDatabase(db_path)
        self.chain = AuditChain()
        self.anchor = AuditAnchor(anchor_path)
        
        # Recover chain state
        latest = self.db.get_chain_hash()
        if latest:
            self.chain._current_hash = latest
        self.sequence = len(self.anchor.read_anchors())

    def log_event(self, session_id: str, agent: str, tool: str, args: dict, policy_decision: str, approval_decision: str, result_summary: str) -> str:
        args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode("utf-8")).hexdigest()
        
        record = AuditRecord(
            timestamp=time.time(),
            session_id=session_id,
            agent=agent,
            tool=tool,
            arguments_hash=args_hash,
            policy_decision=policy_decision,
            approval_decision=approval_decision,
            result_summary=result_summary
        )
        
        event_data = f"{record.timestamp}|{session_id}|{agent}|{tool}|{args_hash}|{policy_decision}|{approval_decision}|{result_summary}"
        chain_hash = self.chain.add_event(event_data)
        
        self.db.record(record, chain_hash)
        
        self.sequence += 1
        self.anchor.write_anchor(record.timestamp, self.sequence, chain_hash)
        
        return record.event_id

    def verify_integrity(self) -> bool:
        # Check if the latest hash in DB matches the anchor
        db_hash = self.db.get_chain_hash()
        if db_hash is None:
            db_hash = ""
        return self.anchor.verify_latest(db_hash)

    def close(self):
        self.db.close()
