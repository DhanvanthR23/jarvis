"""Voice confirmation logic (G24.8)."""

import re

from jarvis.voice.session import VoiceSession
from jarvis.voice.stt.interface import Transcript

CONFIRMATION_PATTERN = re.compile(r'(?i)yes jarvis,? confirm')

def is_confirmation(transcript: Transcript) -> bool:
    return bool(CONFIRMATION_PATTERN.search(transcript.text))

def process_confirmation(transcript: Transcript, session: VoiceSession, min_confidence: float = 0.8) -> dict:
    """Process a voice confirmation attempt."""
    # 1. Confidence check (Invariant O)
    # NOTE: The 0.8 min_confidence threshold is an empirical/operational tuning value 
    # chosen from testing, not a security guarantee. It does NOT authenticate the speaker 
    # (per Invariant M) and must never be described or relied upon as proof of speaker identity.
    if transcript.confidence < min_confidence:
        # Invariant O: fails closed, does not consume, does not extend, records failure
        # But which approval? We don't know if ambiguous. We apply failure to ALL pending?
        # Actually, if confidence is low, we don't know what they said. But if we matched the regex
        # despite low confidence, we reject the attempt.
        # "insufficient STT confidence on a confirmation rejects that attempt only"
        pending = session.get_all_pending()
        for p in pending:
            p.record_failed_attempt()
        return {'status': 'rejected', 'reason': 'insufficient_confidence'}

    pending = session.get_all_pending()
    if not pending:
        return {'status': 'rejected', 'reason': 'no_pending_approvals'}

    if len(pending) > 1:
        # Multiple simultaneous approvals (Invariant: no cross-resolve)
        return {'status': 'ambiguous', 'reason': 'multiple_pending'}

    # Exactly one pending
    approval = pending[0]
    
    # Check freshness/validity
    if not approval.is_valid():
        return {'status': 'rejected', 'reason': 'invalid_or_expired'}
        
    # Valid!
    approval.consume()
    return {'status': 'confirmed', 'approval': approval}

