import os

files = {}

files['/home/dhanvanth/projects/jarvis/jarvis/policy/__init__.py'] = ''

files['/home/dhanvanth/projects/jarvis/jarvis/policy/capabilities.toml'] = '''\
[meta]
version = "0.1.0"

[capabilities]
system_info = "safe"
system_temperature = "safe"
network_interfaces = "safe"
network_status = "safe"
processes_list = "safe"
logs_search = "safe"
files_read = "safe"
files_search = "safe"

files_write = "approval"
service_restart = "approval"
package_install = "approval"
memory_write = "approval"

arbitrary_shell = "disabled"
sudo = "disabled"
'''

files['/home/dhanvanth/projects/jarvis/jarvis/policy/manifest.py'] = '''\
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import Dict
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # For python < 3.11, not ideal but for the sake of completion

class RiskTier(Enum):
    SAFE = "safe"
    APPROVAL = "approval"
    DISABLED = "disabled"

@dataclass
class Capability:
    name: str
    risk_tier: RiskTier
    description: str

class ManifestIntegrityError(Exception):
    pass

class CapabilityManifest:
    def __init__(self, path: str):
        self.path = path
        self.capabilities: Dict[str, Capability] = {}
        self.version = ""
        self._raw_content = b""

    def load(self) -> dict:
        with open(self.path, "rb") as f:
            self._raw_content = f.read()
            data = tomllib.loads(self._raw_content.decode('utf-8'))
        
        self.version = data.get("meta", {}).get("version", "unknown")
        caps = data.get("capabilities", {})
        for name, tier_str in caps.items():
            self.capabilities[name] = Capability(name=name, risk_tier=RiskTier(tier_str), description="")
        return data

    def compute_hash(self) -> str:
        return hashlib.sha256(self._raw_content).hexdigest()

    def verify_integrity(self, trusted_hash: str) -> bool:
        if not self._raw_content:
            with open(self.path, "rb") as f:
                self._raw_content = f.read()
        return self.compute_hash() == trusted_hash

def load_manifest(path: str, trusted_hash: str) -> CapabilityManifest:
    manifest = CapabilityManifest(path)
    if not manifest.verify_integrity(trusted_hash):
        raise ManifestIntegrityError("Hash mismatch")
    manifest.load()
    return manifest
'''

files['/home/dhanvanth/projects/jarvis/jarvis/policy/trusted_hash.py'] = '''\
import hashlib

TRUSTED_HASH: str = ''

def compute_and_store_hash(manifest_path: str, hash_file_path: str):
    with open(manifest_path, "rb") as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    with open(hash_file_path, "w") as f:
        f.write(file_hash)

def load_trusted_hash(hash_file_path: str) -> str:
    with open(hash_file_path, "r") as f:
        return f.read().strip()
'''

files['/home/dhanvanth/projects/jarvis/jarvis/policy/engine.py'] = '''\
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
'''

files['/home/dhanvanth/projects/jarvis/jarvis/policy/approval.py'] = '''\
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
        print(f"\\n--- APPROVAL REQUIRED ---")
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
'''

files['/home/dhanvanth/projects/jarvis/tests/policy/__init__.py'] = ''

files['/home/dhanvanth/projects/jarvis/tests/policy/test_manifest.py'] = '''\
import os
import tempfile
import unittest
from jarvis.policy.manifest import CapabilityManifest, load_manifest, ManifestIntegrityError, RiskTier
from jarvis.policy.trusted_hash import compute_and_store_hash, load_trusted_hash

class TestManifest(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        with os.fdopen(self.fd, "w") as f:
            f.write("""[meta]\\nversion = "1.0"\\n[capabilities]\\ntest_safe = "safe"\\ntest_approve = "approval"\\ntest_disabled = "disabled"\\n""")
        self.hash_fd, self.hash_path = tempfile.mkstemp()
        os.close(self.hash_fd)
        compute_and_store_hash(self.path, self.hash_path)
        self.trusted_hash = load_trusted_hash(self.hash_path)
            
    def tearDown(self):
        os.remove(self.path)
        os.remove(self.hash_path)

    def test_load_manifest(self):
        man = CapabilityManifest(self.path)
        man.load()
        self.assertEqual(man.capabilities["test_safe"].risk_tier, RiskTier.SAFE)

    def test_verify_integrity(self):
        man = CapabilityManifest(self.path)
        self.assertTrue(man.verify_integrity(self.trusted_hash))
        
    def test_verify_integrity_fails(self):
        man = CapabilityManifest(self.path)
        self.assertFalse(man.verify_integrity("wrong_hash"))
        
    def test_load_manifest_function(self):
        man = load_manifest(self.path, self.trusted_hash)
        self.assertIn("test_safe", man.capabilities)
        
    def test_manifest_integrity_error(self):
        with self.assertRaises(ManifestIntegrityError):
            load_manifest(self.path, "wrong_hash")
'''

files['/home/dhanvanth/projects/jarvis/tests/policy/test_engine.py'] = '''\
import os
import tempfile
import unittest
from jarvis.policy.manifest import CapabilityManifest
from jarvis.policy.engine import PolicyEngine, PolicyDecision

class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        with os.fdopen(self.fd, "w") as f:
            f.write("""[meta]\\nversion = "1.0"\\n[capabilities]\\ntest_safe = "safe"\\ntest_approve = "approval"\\ntest_disabled = "disabled"\\n""")
        self.man = CapabilityManifest(self.path)
        self.man.load()
        self.engine = PolicyEngine(self.man)
        
    def tearDown(self):
        os.remove(self.path)

    def test_safe_capability(self):
        res = self.engine.check("test_safe")
        self.assertEqual(res.decision, PolicyDecision.ALLOW)
        
    def test_approve_capability(self):
        res = self.engine.check("test_approve")
        self.assertEqual(res.decision, PolicyDecision.APPROVE)
        
    def test_disabled_capability(self):
        res = self.engine.check("test_disabled")
        self.assertEqual(res.decision, PolicyDecision.DENY)
        
    def test_unknown_capability(self):
        res = self.engine.check("unknown")
        self.assertEqual(res.decision, PolicyDecision.DENY)
'''

files['/home/dhanvanth/projects/jarvis/tests/policy/test_approval.py'] = '''\
import unittest
from jarvis.policy.approval import ApprovalRequest, AutoDenyHandler, SessionApprovalCache, ApprovalDecision

class TestApproval(unittest.TestCase):
    def test_auto_deny(self):
        handler = AutoDenyHandler()
        req = ApprovalRequest("actor", "cap", "target", {}, "reason", "high")
        res = handler.request_approval(req)
        self.assertEqual(res.decision, ApprovalDecision.DENY)
        
    def test_session_cache_allow_session(self):
        cache = SessionApprovalCache()
        cache.add_approval("cap1", ApprovalDecision.ALLOW_SESSION)
        self.assertTrue(cache.is_approved("cap1"))
        
    def test_session_cache_allow_once(self):
        cache = SessionApprovalCache()
        cache.add_approval("cap2", ApprovalDecision.ALLOW_ONCE)
        self.assertFalse(cache.is_approved("cap2"))
'''

for path, content in files.items():
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)

