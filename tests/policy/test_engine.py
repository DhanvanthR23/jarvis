import os
import tempfile
import unittest
from jarvis.policy.manifest import CapabilityManifest
from jarvis.policy.engine import PolicyEngine, PolicyDecision

class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        with os.fdopen(self.fd, "w") as f:
            f.write("""[meta]\nversion = "1.0"\n[capabilities]\ntest_safe = "safe"\ntest_approve = "approval"\ntest_disabled = "disabled"\n""")
        self.man = CapabilityManifest(self.path)
        self.man.load()
        self.engine = PolicyEngine(self.man, active_role=None)
        
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
