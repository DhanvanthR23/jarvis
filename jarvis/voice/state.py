"""Voice state machine (plan2.md section 3).

Deterministic state transitions for the voice runtime.
"""
from enum import Enum, auto


class VoiceState(Enum):
    """States of the voice runtime state machine."""
    IDLE = auto()
    LISTENING = auto()
    STT = auto()
    PROCESSING = auto()
    WAITING_APPROVAL = auto()
    EXECUTING = auto()
    SPEAKING = auto()


# Valid transitions: (from_state, to_state)
VALID_TRANSITIONS = frozenset({
    (VoiceState.IDLE, VoiceState.LISTENING),
    (VoiceState.LISTENING, VoiceState.STT),
    (VoiceState.LISTENING, VoiceState.IDLE),          # timeout / silence
    (VoiceState.STT, VoiceState.PROCESSING),
    (VoiceState.STT, VoiceState.IDLE),                # STT failure
    (VoiceState.PROCESSING, VoiceState.EXECUTING),
    (VoiceState.PROCESSING, VoiceState.WAITING_APPROVAL),
    (VoiceState.PROCESSING, VoiceState.SPEAKING),     # direct response (no tool)
    (VoiceState.PROCESSING, VoiceState.IDLE),         # processing failure
    (VoiceState.WAITING_APPROVAL, VoiceState.LISTENING),   # prompt for confirmation
    (VoiceState.WAITING_APPROVAL, VoiceState.EXECUTING),   # approval granted
    (VoiceState.WAITING_APPROVAL, VoiceState.SPEAKING),    # approval denied → speak denial
    (VoiceState.WAITING_APPROVAL, VoiceState.IDLE),        # expiration
    (VoiceState.EXECUTING, VoiceState.SPEAKING),
    (VoiceState.EXECUTING, VoiceState.IDLE),          # execution failure
    (VoiceState.SPEAKING, VoiceState.IDLE),
    (VoiceState.SPEAKING, VoiceState.LISTENING),      # interruption
})


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class VoiceStateMachine:
    """Deterministic voice state machine.

    Every transition is validated against VALID_TRANSITIONS.
    Invalid transitions raise InvalidTransitionError — no silent fallthrough.
    """

    def __init__(self):
        self._state = VoiceState.IDLE

    @property
    def state(self) -> VoiceState:
        return self._state

    def transition(self, new_state: VoiceState) -> None:
        """Attempt a state transition.

        Args:
            new_state: The target state.

        Raises:
            InvalidTransitionError: If the transition is not in VALID_TRANSITIONS.
        """
        pair = (self._state, new_state)
        if pair not in VALID_TRANSITIONS:
            raise InvalidTransitionError(
                f"Invalid transition: {self._state.name} → {new_state.name}"
            )
        self._state = new_state

    def reset(self) -> None:
        """Force-reset to IDLE. Used only for error recovery."""
        self._state = VoiceState.IDLE
