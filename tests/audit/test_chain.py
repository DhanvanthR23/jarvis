import unittest
from jarvis.audit.chain import AuditChain, compute_event_hash

class TestAuditChain(unittest.TestCase):
    def test_compute_event_hash(self):
        h1 = compute_event_hash("ev1", "")
        self.assertTrue(len(h1) > 0)
        
    def test_chain_sequence(self):
        chain = AuditChain()
        h1 = chain.add_event("ev1")
        h2 = chain.add_event("ev2")
        self.assertNotEqual(h1, h2)
        
    def test_verify_chain(self):
        chain = AuditChain()
        h1 = chain.add_event("ev1")
        h2 = chain.add_event("ev2")
        self.assertTrue(chain.verify_chain(["ev1", "ev2"], [h1, h2]))
        self.assertFalse(chain.verify_chain(["ev1", "ev2_tampered"], [h1, h2]))
