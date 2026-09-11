"""End-to-End Read-Only Voice Test (plan2.md section 27, G24.15).

Verifies a read-only command completes the full pipeline without triggering approval.
"""
import unittest
from jarvis.core.controller import JarvisController
from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep
from jarvis.voice.runtime import VoiceRuntime
from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech
from jarvis.output.filter import OutputSecurityFilter
from jarvis.policy.engine import PolicyEngine
from jarvis.policy.manifest import CapabilityManifest, Capability, RiskTier

class MockSTTE2E(SpeechToText):
    def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text="what is the time", confidence=0.99)
    def is_available(self) -> bool: return True

class MockTTSE2E(TextToSpeech):
    def __init__(self):
        self.spoken = []
    def speak(self, text: str) -> None:
        self.spoken.append(text)
    def stop(self) -> None: pass
    def is_available(self) -> bool: return True

class TestVoiceE2EReadOnly(unittest.TestCase):
    def test_e2e_readonly_pipeline(self):
        # 1. Setup policy (safe tool)
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {'get_time': Capability('get_time', RiskTier.SAFE)}
        manifest._loaded = True
        policy = PolicyEngine(manifest, active_role=None)

        # 2. Setup Agent
        scenario = ScriptedScenario(
            trigger="time",
            steps=[ScriptedStep("get_time", {})],
            response="The time is 12:00 PM."
        )
        agent = MockAgent([scenario])

        # 3. Setup Controller
        ctrl = JarvisController(
            agent_backend=agent,
            policy_engine=policy,
            output_filter=OutputSecurityFilter()
        )
        
        # Add mock tool
        tool_called = False
        def mock_get_time():
            nonlocal tool_called
            tool_called = True
            return "12:00 PM"
        ctrl.register_tool('get_time', mock_get_time)

        # 4. Setup Voice Runtime
        cap = MockAudioCapture()
        pb = MockAudioPlayback()
        stt = MockSTTE2E()
        tts = MockTTSE2E()
        runtime = VoiceRuntime(cap, pb, stt, tts)
        
        # Connect VoiceRuntime -> Controller -> VoiceRuntime
        def on_transcription(transcript):
            response = ctrl.process_request(transcript.text, is_voice=True, transcript=transcript)
            runtime.speak(response)
            
        runtime.on_transcription = on_transcription

        # 5. EXECUTE PIPELINE
        # Wake up
        runtime.start_listening()
        self.assertTrue(cap._recording)
        
        # User speaks (simulated by stop_listening capturing the audio)
        runtime.stop_listening()
        
        # 6. ASSERTIONS
        # The agent should have called the tool
        self.assertTrue(tool_called)
        # TTS should have spoken the response
        self.assertEqual(len(tts.spoken), 1)
        self.assertEqual(tts.spoken[0], "The time is 12:00 PM.")
        # Runtime should be back to IDLE
        self.assertEqual(runtime.state.name, 'IDLE')

if __name__ == '__main__':
    unittest.main()
