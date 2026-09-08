import unittest
from jarvis.security.invariants import (
    INVARIANTS,
    EXPECTED_INVARIANT_IDS,
    EXPECTED_THREATS,
    SecurityInvariant
)

class TestInvariants(unittest.TestCase):
    def test_expected_invariant_ids(self):
        self.assertEqual(set(INVARIANTS.keys()), set(EXPECTED_INVARIANT_IDS))
        self.assertEqual(len(EXPECTED_INVARIANT_IDS), 17)
        for expected_id in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]:
            self.assertIn(expected_id, EXPECTED_INVARIANT_IDS)

    def test_expected_threats(self):
        self.assertGreater(len(EXPECTED_THREATS), 0)
        
    def test_invariant_fields(self):
        for inv_id, inv in INVARIANTS.items():
            self.assertTrue(inv.id)
            self.assertTrue(inv.name)
            self.assertTrue(inv.description)
            self.assertEqual(inv_id, inv.id)

    def test_invariant_immutable(self):
        inv = list(INVARIANTS.values())[0]
        with self.assertRaises(Exception):
            inv.name = "Modified"
