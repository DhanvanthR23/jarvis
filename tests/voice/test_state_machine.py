"""Tests for voice state machine (plan2.md section 3)."""
import unittest

from jarvis.voice.state import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    VoiceState,
    VoiceStateMachine,
)


class TestVoiceStateMachine(unittest.TestCase):

    def test_initial_state_is_idle(self):
        sm = VoiceStateMachine()
        self.assertEqual(sm.state, VoiceState.IDLE)

    def test_valid_transition_idle_to_listening(self):
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        self.assertEqual(sm.state, VoiceState.LISTENING)

    def test_invalid_transition_raises(self):
        sm = VoiceStateMachine()
        with self.assertRaises(InvalidTransitionError):
            sm.transition(VoiceState.SPEAKING)

    def test_full_read_only_path(self):
        """IDLE → LISTENING → STT → PROCESSING → SPEAKING → IDLE"""
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        sm.transition(VoiceState.STT)
        sm.transition(VoiceState.PROCESSING)
        sm.transition(VoiceState.SPEAKING)
        sm.transition(VoiceState.IDLE)

    def test_approval_path(self):
        """IDLE → LISTENING → STT → PROCESSING → WAITING_APPROVAL → LISTENING"""
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        sm.transition(VoiceState.STT)
        sm.transition(VoiceState.PROCESSING)
        sm.transition(VoiceState.WAITING_APPROVAL)
        sm.transition(VoiceState.LISTENING)

    def test_approval_to_executing(self):
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        sm.transition(VoiceState.STT)
        sm.transition(VoiceState.PROCESSING)
        sm.transition(VoiceState.WAITING_APPROVAL)
        sm.transition(VoiceState.EXECUTING)
        sm.transition(VoiceState.SPEAKING)
        sm.transition(VoiceState.IDLE)

    def test_interruption_speaking_to_listening(self):
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        sm.transition(VoiceState.STT)
        sm.transition(VoiceState.PROCESSING)
        sm.transition(VoiceState.SPEAKING)
        sm.transition(VoiceState.LISTENING)

    def test_reset_returns_to_idle(self):
        sm = VoiceStateMachine()
        sm.transition(VoiceState.LISTENING)
        sm.reset()
        self.assertEqual(sm.state, VoiceState.IDLE)

    def test_cannot_skip_states(self):
        sm = VoiceStateMachine()
        with self.assertRaises(InvalidTransitionError):
            sm.transition(VoiceState.PROCESSING)  # can't skip LISTENING→STT

    def test_all_valid_transitions_succeed(self):
        for from_state, to_state in VALID_TRANSITIONS:
            sm = VoiceStateMachine()
            sm._state = from_state  # force state for exhaustive check
            sm.transition(to_state)
            self.assertEqual(sm.state, to_state)


class TestVoiceStateMachineExhaustive(unittest.TestCase):

    def test_every_non_valid_pair_raises(self):
        """Every (from, to) pair NOT in VALID_TRANSITIONS must raise."""
        all_states = list(VoiceState)
        for from_state in all_states:
            for to_state in all_states:
                if (from_state, to_state) not in VALID_TRANSITIONS:
                    sm = VoiceStateMachine()
                    sm._state = from_state
                    with self.assertRaises(InvalidTransitionError,
                                           msg=f"{from_state}→{to_state} should be invalid"):
                        sm.transition(to_state)


if __name__ == '__main__':
    unittest.main()
