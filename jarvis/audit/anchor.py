import os

class AuditAnchor:
    def __init__(self, anchor_path: str):
        self.anchor_path = anchor_path

    def write_anchor(self, timestamp: float, sequence: int, chain_hash: str):
        with open(self.anchor_path, "a") as f:
            f.write(f"{timestamp}|{sequence}|{chain_hash}\n")

    def read_anchors(self) -> list:
        if not os.path.exists(self.anchor_path):
            return []
        anchors = []
        with open(self.anchor_path, "r") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 3:
                    anchors.append({
                        "timestamp": float(parts[0]),
                        "sequence": int(parts[1]),
                        "chain_hash": parts[2]
                    })
        return anchors

    def verify_latest(self, expected_hash: str) -> bool:
        anchors = self.read_anchors()
        if not anchors:
            return expected_hash == ""
        return anchors[-1]["chain_hash"] == expected_hash
