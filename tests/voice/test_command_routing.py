"""Tests for Voice -> Controller integration (G24.7)."""
import unittest
from jarvis.core.controller import JarvisController
from jarvis.agent.mock import MockAgent, ScriptedScenario
from jarvis.output.filter import OutputSecurityFilter, SAFE_REPLACEMENT
from jarvis.voice.stt.interface import Transcript

class TestVoiceControllerIntegration(unittest.TestCase):
    def setUp(self):
        scenario = ScriptedScenario(
            trigger="key",
            steps=[],
            response="Here is the api_key: sk-12345678901234567890"
        )
        self.agent = MockAgent([scenario])
        self.output_filter = OutputSecurityFilter()
        self.controller = JarvisController(
            agent_backend=self.agent,
            output_filter=self.output_filter
        )

    def test_process_voice_request_filters_output(self):
        # If AGY returns a secret in freeform text, it should be blocked.
        transcript = Transcript(text="What is the key?", confidence=0.95)
        
        response = self.controller.process_voice_request(transcript)
        
        # Should be replaced by the output filter
        self.assertEqual(response, SAFE_REPLACEMENT)
        self.assertNotIn("sk-", response)

    def test_process_request_filters_output(self):
        # CLI requests also go through the filter
        response = self.controller.process_request("What is the key?")
        
        self.assertEqual(response, SAFE_REPLACEMENT)
        self.assertNotIn("sk-", response)

    def test_voice_cannot_bypass_policy(self):
        # Even if voice transcription returns something, policy blocks tool execution
        from jarvis.policy.engine import PolicyEngine
        from jarvis.core.events import EventType
        from jarvis.agent.mock import ScriptedStep, ScriptedScenario
        
        # Disable command_execute in policy
        from jarvis.policy.manifest import CapabilityManifest, Capability, RiskTier
        manifest = CapabilityManifest('dummy')
        manifest._capabilities = {'command_execute': Capability('command_execute', RiskTier.DISABLED)}
        manifest._loaded = True
        self.controller.policy_engine = PolicyEngine(manifest)
        
        # AGY tries to execute the tool
        scenario = ScriptedScenario(
            trigger="run",
            steps=[ScriptedStep("command_execute", {"cmd": "ls"})],
            response="I ran it: {}"
        )
        self.controller.agent_backend = MockAgent([scenario])
        
        transcript = Transcript(text="run a command", confidence=0.99)
        self.controller.process_voice_request(transcript)
        
        # Check that the policy check event was logged and the agent response reflects the denial
        policy_checks = [e for e in self.controller.session.events if e.type == EventType.POLICY_CHECK]
        self.assertTrue(len(policy_checks) > 0)
        
        agent_responses = [e for e in self.controller.session.events if e.type == EventType.AGENT_RESPONSE]
        self.assertIn("denied", agent_responses[0].data['response'])

if __name__ == '__main__':
    unittest.main()

