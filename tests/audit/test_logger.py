import os
import tempfile
import unittest
from jarvis.audit.logger import AuditLogger

class TestAuditLogger(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.anch_fd, self.anch_path = tempfile.mkstemp()
        os.close(self.db_fd)
        os.close(self.anch_fd)
        self.logger = AuditLogger(self.db_path, self.anch_path)
        
    def tearDown(self):
        self.logger.close()
        os.remove(self.db_path)
        os.remove(self.anch_path)
        
    def test_log_event_and_verify(self):
        self.logger.log_event("s1", "a1", "t1", {"a": 1}, "ALLOW", None, "res")
        self.assertTrue(self.logger.verify_integrity())
