"""Voice runtime orchestrator (plan2.md section 3 & 20).

Orchestrates the VoiceStateMachine, AudioCapture, STT, TTS, and AudioPlayback.
Handles transition events.
"""
import threading
from typing import Optional, Callable

from jarvis.voice.state import VoiceState, VoiceStateMachine, InvalidTransitionError
from jarvis.voice.audio import AudioCapture, AudioPlayback
from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech


class VoiceRuntime:
    """Orchestrates the voice interaction lifecycle."""

    def __init__(
        self,
        capture: AudioCapture,
        playback: AudioPlayback,
        stt: SpeechToText,
        tts: TextToSpeech,
    ):
        self.capture = capture
        self.playback = playback
        self.stt = stt
        self.tts = tts
        self.state_machine = VoiceStateMachine()
        
        # Callback when transcription is ready for the controller
        # Signature: on_transcription(transcript: Transcript) -> None
        self.on_transcription: Optional[Callable[[Transcript], None]] = None

    @property
    def state(self) -> VoiceState:
        return self.state_machine.state

    def start_listening(self) -> None:
        """Transition IDLE -> LISTENING and start mic."""
        self.state_machine.transition(VoiceState.LISTENING)
        self.capture.start()

    def stop_listening(self) -> None:
        """Transition LISTENING -> STT, stop mic, and run STT."""
        self.state_machine.transition(VoiceState.STT)
        chunk = self.capture.stop()
        
        try:
            transcript = self.stt.transcribe(chunk.data)
            # We don't log the raw audio, and `chunk` is dropped here.
            self.state_machine.transition(VoiceState.PROCESSING)
            if self.on_transcription:
                self.on_transcription(transcript)
        except Exception:
            # STT failure
            self.state_machine.transition(VoiceState.IDLE)
            raise

    def speak(self, text: str) -> None:
        """Transition to SPEAKING and synthesize text."""
        # We can enter SPEAKING from PROCESSING, EXECUTING, or WAITING_APPROVAL
        self.state_machine.transition(VoiceState.SPEAKING)
        self.tts.speak(text)
        # Assuming synchronous speak for MVP, transition back to IDLE
        self.state_machine.transition(VoiceState.IDLE)

    def interrupt(self) -> None:
        """Interrupt TTS and transition to LISTENING."""
        # Can only interrupt if SPEAKING
        if self.state == VoiceState.SPEAKING:
            self.tts.stop()
            self.state_machine.transition(VoiceState.LISTENING)
            self.capture.start()

    def timeout(self) -> None:
        """Handle silence timeout while LISTENING."""
        if self.state == VoiceState.LISTENING:
            self.capture.stop()
            self.state_machine.transition(VoiceState.IDLE)
