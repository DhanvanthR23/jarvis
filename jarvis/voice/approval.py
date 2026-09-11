"""Voice Approval Handler (G24.8).

Integrates with JarvisController to suspend execution and create a 
VoicePendingApproval in the VoiceSession.
"""
import time

from jarvis.policy.approval import (
    ApprovalDecision,
    ApprovalHandler,
    ApprovalRequest,
    ApprovalResponse,
)
from jarvis.voice.session import VoiceSession


class VoiceApprovalHandler(ApprovalHandler):
    """Creates a pending voice approval instead of blocking on input."""

    def __init__(self, voice_session: VoiceSession):
        self.voice_session = voice_session

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Create a pending approval and return DENY to the agent with instructions."""
        
        # Create pending approval
        self.voice_session.create_approval(
            capability=request.capability,
            arguments=request.arguments
        )
        
        # We must return a response to the controller. We can't suspend the Python thread.
        # We return DENY with a special message so the agent knows to prompt the user.
        # This isn't a final DENY, it's just denying this immediate synchronous execution.
        return ApprovalResponse(
            request_id=request.request_id,
            decision=ApprovalDecision.PENDING,
            responded_at=time.time(),
            responded_by="voice_system",
        )
