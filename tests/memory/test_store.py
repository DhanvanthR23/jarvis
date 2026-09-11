import os
import tempfile
import time
import unittest

from jarvis.memory.store import MemoryCategory, MemoryEntry, MemoryStore


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        os.close(self.fd)
        self.store = MemoryStore(self.path)
        
    def tearDown(self):
        self.store.close()
        os.remove(self.path)
        
    def test_write_and_read(self):
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        self.store.write(entry)
        res = self.store.read("k1")
        self.assertEqual(res.value, "v1")
        
    def test_search(self):
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        self.store.write(entry)
        res = self.store.search(category=MemoryCategory.FACTS)
        self.assertEqual(len(res), 1)
        
    def test_delete(self):
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "explicit")
        self.store.write(entry)
        self.assertTrue(self.store.delete("k1"))
        self.assertIsNone(self.store.read("k1"))
        
    def test_list_pending(self):
        entry = MemoryEntry("k1", "v1", MemoryCategory.FACTS, "sys", time.time(), time.time(), "pending")
        self.store.write(entry)
        res = self.store.list_pending()
        self.assertEqual(len(res), 1)
