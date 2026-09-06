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
