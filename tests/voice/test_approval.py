import unittest
import time
from jarvis.voice.session import VoiceSession
from jarvis.voice.confirmation import process_confirmation
from jarvis.voice.stt.interface import Transcript

class TestVoiceApprovals(unittest.TestCase):
    def setUp(self):
        self.session = VoiceSession()

    def test_voice_approval_is_request_bound(self):
        app = self.session.create_approval('test.tool', {'arg': 1})
        self.assertEqual(len(self.session.get_all_pending()), 1)
        
        t = Transcript("yes jarvis confirm", 0.9)
        res = process_confirmation(t, self.session)
        self.assertEqual(res['status'], 'confirmed')
        self.assertEqual(res['approval'], app)
        self.assertTrue(app.consumed)
        
        # Now it is consumed, cannot be used again
        res2 = process_confirmation(t, self.session)
        self.assertEqual(res2['status'], 'rejected')

    def test_low_confidence_confirmation_does_not_approve(self):
        app = self.session.create_approval('test.tool', {'arg': 1})
        t = Transcript("yes jarvis confirm", 0.5) # below 0.8
        res = process_confirmation(t, self.session)
        
        self.assertEqual(res['status'], 'rejected')
        self.assertEqual(res['reason'], 'insufficient_confidence')
        self.assertFalse(app.consumed)
        
    def test_low_confidence_confirmation_keeps_approval_pending(self):
        app = self.session.create_approval('test.tool', {'arg': 1})
        t = Transcript("yes jarvis confirm", 0.5)
        process_confirmation(t, self.session)
        
        self.assertFalse(app.denied)
        self.assertEqual(app.failed_attempts, 1)
        
        # Valid confirmation later succeeds
        t2 = Transcript("yes jarvis confirm", 0.9)
        res = process_confirmation(t2, self.session)
        self.assertEqual(res['status'], 'confirmed')

    def test_three_failed_confirmations_deny_approval(self):
        app = self.session.create_approval('test.tool', {'arg': 1})
        t = Transcript("yes jarvis confirm", 0.5)
        
        process_confirmation(t, self.session)
        process_confirmation(t, self.session)
        self.assertFalse(app.denied)
        
        process_confirmation(t, self.session)
        self.assertTrue(app.denied)
        
        # Fourth attempt with high confidence is rejected
        t2 = Transcript("yes jarvis confirm", 0.9)
        res = process_confirmation(t2, self.session)
        self.assertEqual(res['status'], 'rejected')

    def test_failed_confirmation_does_not_extend_expiration(self):
        app = self.session.create_approval('test.tool', {'arg': 1})
        app.expires_at = time.time() + 0.1 # short expiry
        
        t = Transcript("yes jarvis confirm", 0.5)
        process_confirmation(t, self.session)
        
        self.assertLess(app.expires_at, time.time() + 0.2)
        
        time.sleep(0.15)
        self.assertTrue(app.is_expired())

    def test_multiple_pending_voice_approvals_are_unambiguous(self):
        self.session.create_approval('test.tool', {'arg': 1})
        self.session.create_approval('test.tool2', {'arg': 2})
        
        t = Transcript("yes jarvis confirm", 0.9)
        res = process_confirmation(t, self.session)
        self.assertEqual(res['status'], 'ambiguous')
        
    def test_confirmation_cannot_cross_approve_requests(self):
        app1 = self.session.create_approval('test.tool', {'arg': 1})
        app2 = self.session.create_approval('test.tool2', {'arg': 2})
        
        t = Transcript("yes jarvis confirm", 0.9)
        res = process_confirmation(t, self.session)
        self.assertEqual(res['status'], 'ambiguous')
        
        self.assertFalse(app1.consumed)
        self.assertFalse(app2.consumed)

if __name__ == '__main__':
    unittest.main()
