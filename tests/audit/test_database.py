import os
import tempfile
import unittest
import time
from jarvis.audit.database import AuditDatabase, AuditRecord

class TestAuditDatabase(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        os.close(self.fd)
        self.db = AuditDatabase(self.path)
        
    def tearDown(self):
        self.db.close()
        os.remove(self.path)
        
    def test_record_and_get_latest(self):
        rec = AuditRecord(time.time(), "s1", "a1", "t1", "hash", "allow", "res", "app")
        self.db.record(rec, "chain1")
        latest = self.db.get_latest()
        self.assertEqual(latest["event_id"], rec.event_id)
        self.assertEqual(latest["chain_hash"], "chain1")
        self.assertEqual(self.db.get_chain_hash(), "chain1")
