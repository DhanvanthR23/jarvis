import os
import tempfile
import unittest
from jarvis.audit.anchor import AuditAnchor

class TestAuditAnchor(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        os.close(self.fd)
        self.anchor = AuditAnchor(self.path)
        
    def tearDown(self):
        os.remove(self.path)
        
    def test_write_and_read(self):
        self.anchor.write_anchor(1.0, 1, "hash1")
        self.anchor.write_anchor(2.0, 2, "hash2")
        anchors = self.anchor.read_anchors()
        self.assertEqual(len(anchors), 2)
        self.assertEqual(anchors[-1]["chain_hash"], "hash2")
        
    def test_verify_latest(self):
        self.anchor.write_anchor(1.0, 1, "hash1")
        self.assertTrue(self.anchor.verify_latest("hash1"))
        self.assertFalse(self.anchor.verify_latest("hash2"))
