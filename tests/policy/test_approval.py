import time
import unittest

from jarvis.policy.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResponse,
    SessionApprovalCache,
)


class TestApprovalSystem(unittest.TestCase):

    def test_argument_binding(self):
        cache = SessionApprovalCache()
        
        req1 = ApprovalRequest("actor", "files.write", {"path": "/a", "content": "safe"}, "reason", "risk")
        resp1 = ApprovalResponse(req1.request_id, ApprovalDecision.ALLOW_SESSION, time.time(), "user")
        cache.add_approval(req1, resp1)
        
        self.assertTrue(cache.is_approved(req1))
        
        # Test modifying the arguments
        req2 = ApprovalRequest("actor", "files.write", {"path": "/etc/passwd", "content": "malicious"}, "reason", "risk")
        self.assertFalse(cache.is_approved(req2))
        
        # Test exact same arguments but different capability
        req3 = ApprovalRequest("actor", "files.read", {"path": "/a", "content": "safe"}, "reason", "risk")
        self.assertFalse(cache.is_approved(req3))

    def test_allow_once(self):
        cache = SessionApprovalCache()
        req1 = ApprovalRequest("actor", "files.write", {"path": "/a"}, "reason", "risk")
        resp1 = ApprovalResponse(req1.request_id, ApprovalDecision.ALLOW_ONCE, time.time(), "user")
        cache.add_approval(req1, resp1)
        
        # ALLOW_ONCE should NOT be cached
        self.assertFalse(cache.is_approved(req1))

    def test_expiration(self):
        cache = SessionApprovalCache()
        req1 = ApprovalRequest("actor", "files.write", {"path": "/a"}, "reason", "risk")
        
        # Expires immediately
        resp1 = ApprovalResponse(req1.request_id, ApprovalDecision.ALLOW_SESSION, time.time(), "user", expires_at=time.time() - 1)
        cache.add_approval(req1, resp1)
        
        self.assertFalse(cache.is_approved(req1))
