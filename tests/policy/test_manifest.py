import os
import tempfile
import unittest
from jarvis.policy.manifest import CapabilityManifest, load_manifest, ManifestIntegrityError, RiskTier
from jarvis.policy.trusted_hash import compute_and_store_hash, load_trusted_hash

class TestManifest(unittest.TestCase):
    def setUp(self):
        self.fd, self.path = tempfile.mkstemp()
        with os.fdopen(self.fd, "w") as f:
            f.write("""[meta]\nversion = "1.0"\n[capabilities]\ntest_safe = "safe"\ntest_approve = "approval"\ntest_disabled = "disabled"\n""")
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

    def test_manifest_corrupted_file(self):
        # Corrupt the file by one byte
        with open(self.path, 'a') as f:
            f.write("x")
        
        # Must refuse to start (raise ManifestIntegrityError) and not continue
        with self.assertRaises(ManifestIntegrityError):
            load_manifest(self.path, self.trusted_hash)
