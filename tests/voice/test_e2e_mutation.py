"""End-to-End Mutation Voice Test (plan2.md section 28, G24.16).

Verifies a mutation command is properly suspended, requests voice approval,
and executes only after explicit confirmation.
"""
import unittest

from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep
from jarvis.core.controller import JarvisController
from jarvis.output.filter import OutputSecurityFilter
from jarvis.policy.engine import PolicyEngine
from jarvis.policy.manifest import Capability, CapabilityManifest, RiskTier
from jarvis.voice.approval import VoiceApprovalHandler
from jarvis.voice.audio import MockAudioCapture, MockAudioPlayback
from jarvis.voice.runtime import VoiceRuntime
from jarvis.voice.session import VoiceSession
from jarvis.voice.stt.interface import SpeechToText, Transcript
from jarvis.voice.tts.interface import TextToSpeech


class MockSTTSequence(SpeechToText):
    def __init__(self, transcripts):
        self.transcripts = transcripts
        self.idx = 0
    def transcribe(self, audio: bytes) -> Transcript:
        t = self.transcripts[self.idx]
        self.idx += 1
        return t
    def is_available(self) -> bool: return True

class MockTTSE2E(TextToSpeech):
    def __init__(self):
        self.spoken = []
    def speak(self, text: str) -> None:
        self.spoken.append(text)
    def stop(self) -> None: pass
    def is_available(self) -> bool: return True

class TestVoiceE2EMutation(unittest.TestCase):
    def test_e2e_mutation_pipeline(self):
        # 1. Setup policy (approval tool)
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {'restart_service': Capability('restart_service', RiskTier.APPROVAL)}
        manifest._loaded = True
        policy = PolicyEngine(manifest, active_role=None)

        # 2. Setup Agent
        # MockAgent will just return whatever format we give it.
        # Wait, if tool_callback returns 'pending_approval', MockAgent (as currently written)
        # just puts it into the string.
        scenario = ScriptedScenario(
            trigger="restart",
            steps=[ScriptedStep("restart_service", {"name": "network"})],
            response="Result: {}"
        )
        # We need a second scenario for the confirmation follow-up
        scenario_confirm = ScriptedScenario(
            trigger="proceed",
            steps=[ScriptedStep("restart_service", {"name": "network"})],
            response="Done: {}"
        )
        agent = MockAgent([scenario, scenario_confirm])

        # 3. Setup Voice Session & Controller
        voice_session = VoiceSession()
        approval_handler = VoiceApprovalHandler(voice_session)
        
        ctrl = JarvisController(
            agent_backend=agent,
            policy_engine=policy,
            approval_handler=approval_handler,
            voice_session=voice_session,
            output_filter=OutputSecurityFilter()
        )
        
        # Add mock tool
        tool_called_count = 0
        def mock_restart(name):
            nonlocal tool_called_count
            tool_called_count += 1
            return "restarted"
        ctrl.register_tool('restart_service', mock_restart)

        # 4. Setup Voice Runtime
        cap = MockAudioCapture()
        pb = MockAudioPlayback()
        stt = MockSTTSequence([
            Transcript("restart the network", 0.99),
            Transcript("yes jarvis confirm", 0.95)
        ])
        tts = MockTTSE2E()
        runtime = VoiceRuntime(cap, pb, stt, tts)
        
        def on_transcription(transcript):
            response = ctrl.process_request(transcript.text, is_voice=True, transcript=transcript)
            runtime.speak(response)
            
        runtime.on_transcription = on_transcription

        # 5. EXECUTE PIPELINE
        
        # --- Attempt 1: The Request ---
        runtime.start_listening()
        runtime.stop_listening() # feeds "restart the network"
        
        # The agent should have tried the tool, got 'pending_approval', and spoken it.
        self.assertEqual(tool_called_count, 0)
        self.assertIn("Requires voice confirmation", tts.spoken[0])
        self.assertEqual(len(voice_session.get_all_pending()), 1)
        
        # --- Attempt 2: The Confirmation ---
        runtime.start_listening()
        runtime.stop_listening() # feeds "yes jarvis confirm"
        
        # The agent should have re-invoked the tool (via the confirmation logic injecting to cache)
        self.assertEqual(tool_called_count, 1)
        self.assertIn("restarted", tts.spoken[1])
        self.assertEqual(len(voice_session.get_all_pending()), 0) # Consumed

if __name__ == '__main__':
    unittest.main()
