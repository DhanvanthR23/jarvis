import os
import tempfile
import unittest
import time
from jarvis.memory.store import MemoryStore, MemoryEntry, MemoryCategory
from jarvis.memory.policy import MemoryPolicyEngine, MemoryWriteRequest
from jarvis.policy.approval import AutoDenyHandler, ApprovalDecision, ApprovalResponse

class MockApprovalHandler:
    def request_approval(self, req):
        return ApprovalResponse("1", ApprovalDecision.ALLOW_ONCE, time.time(), "user")

class TestMemoryPolicy(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        os.close(self.fd)
        self.store = MemoryStore(self.path)
        
    def tearDown(self):
        self.store.close()
        os.remove(self.path)

    def test_user_explicit(self):
        engine = MemoryPolicyEngine(self.store)
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req = MemoryWriteRequest(entry, "user_explicit")
        self.assertTrue(engine.process_write(req))
        self.assertEqual(self.store.read("k1").confidence, "explicit")

    def test_agent_inferred(self):
        engine = MemoryPolicyEngine(self.store)
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req = MemoryWriteRequest(entry, "agent_inferred")
        self.assertTrue(engine.process_write(req))
        self.assertEqual(self.store.read("k1").confidence, "pending")

    def test_agent_high_impact_denied(self):
        engine = MemoryPolicyEngine(self.store, approval_handler=AutoDenyHandler())
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req = MemoryWriteRequest(entry, "agent_high_impact")
        self.assertFalse(engine.process_write(req))
        
    def test_agent_high_impact_approved(self):
        engine = MemoryPolicyEngine(self.store, approval_handler=MockApprovalHandler())
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req = MemoryWriteRequest(entry, "agent_high_impact")
        self.assertTrue(engine.process_write(req))
        
    def test_approve_reject_pending(self):
        engine = MemoryPolicyEngine(self.store)
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req = MemoryWriteRequest(entry, "agent_inferred")
        engine.process_write(req)
        
        self.assertTrue(engine.approve_pending("k1"))
        self.assertEqual(self.store.read("k1").confidence, "explicit")
        
        entry2 = MemoryEntry("k2", "v2", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        req2 = MemoryWriteRequest(entry2, "agent_inferred")
        engine.process_write(req2)
        
        self.assertTrue(engine.reject_pending("k2"))
        self.assertIsNone(self.store.read("k2"))
