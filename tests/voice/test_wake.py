"""Tests for Wake Engine (G24.14)."""
import unittest
import time
from jarvis.voice.wake import MockWakeEngine, HotkeyWakeEngine

class TestWakeEngine(unittest.TestCase):
    def test_mock_wake(self):
        woke = False
        def on_wake():
            nonlocal woke
            woke = True
            
        engine = MockWakeEngine(on_wake)
        engine.trigger()
        self.assertFalse(woke) # not started
        
        engine.start()
        engine.trigger()
        self.assertTrue(woke)
        
    def test_hotkey_wake(self):
        woke = False
        def on_wake():
            nonlocal woke
            woke = True
            
        engine = HotkeyWakeEngine(on_wake)
        engine.start()
        engine.trigger()
        
        # Give thread a moment
        time.sleep(0.05)
        self.assertTrue(woke)
        
        engine.stop()

if __name__ == '__main__':
    unittest.main()
