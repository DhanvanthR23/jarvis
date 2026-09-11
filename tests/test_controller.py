"""Tests for Jarvis controller (G6)."""

import unittest
from unittest.mock import MagicMock

from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep
from jarvis.core.controller import JarvisController
from jarvis.core.events import EventType


class TestJarvisController(unittest.TestCase):

    def _make_mock_agent(self):
        return MockAgent([
            ScriptedScenario(
                trigger='test',
                steps=[ScriptedStep('system.info', {})],
                response='Test result: {}',
            ),
        ])

    def test_creation(self):
        agent = self._make_mock_agent()
        ctrl = JarvisController(agent_backend=agent)
        self.assertIsNotNone(ctrl.session)
        self.assertTrue(ctrl.session.is_active)

    def test_process_request_calls_agent(self):
        agent = self._make_mock_agent()
        ctrl = JarvisController(agent_backend=agent)
        response = ctrl.process_request('run test')
        self.assertIn('Test result', response)

    def test_tool_callback_triggers_policy(self):
        agent = self._make_mock_agent()
        mock_policy = MagicMock()
        # Return an ALLOW decision
        mock_result = MagicMock()
        mock_result.decision.value = 'allow'
        mock_result.reason = 'safe capability'
        mock_policy.check.return_value = mock_result

        ctrl = JarvisController(
            agent_backend=agent,
            policy_engine=mock_policy,
        )
        ctrl.process_request('run test')
        mock_policy.check.assert_called()

    def test_tool_callback_skips_policy_when_none(self):
        agent = self._make_mock_agent()
        ctrl = JarvisController(agent_backend=agent, policy_engine=None)
        # Should not raise even without policy engine
        response = ctrl.process_request('run test')
        self.assertIsInstance(response, str)

    def test_events_recorded_in_session(self):
        agent = self._make_mock_agent()
        ctrl = JarvisController(agent_backend=agent)
        ctrl.process_request('run test')
        events = ctrl.session.events
        # Should have at least REQUEST, TOOL_CALL, TOOL_RESULT, AGENT_RESPONSE
        event_types = [e.type for e in events]
        self.assertIn(EventType.REQUEST, event_types)
        self.assertIn(EventType.AGENT_RESPONSE, event_types)

    def test_policy_deny_returns_denied(self):
        agent = self._make_mock_agent()
        mock_policy = MagicMock()
        mock_result = MagicMock()
        mock_result.decision.value = 'deny'
        mock_result.reason = 'capability disabled'
        mock_policy.check.return_value = mock_result

        ctrl = JarvisController(
            agent_backend=agent,
            policy_engine=mock_policy,
        )
        response = ctrl.process_request('run test')
        # The mock agent should still produce a response (it formats the denied result)
        self.assertIsInstance(response, str)

    def test_controller_approval_flow(self):
        agent = self._make_mock_agent()
        mock_policy = MagicMock()
        mock_result = MagicMock()
        mock_result.decision.value = 'approve'
        mock_result.reason = 'high risk'
        mock_policy.check.return_value = mock_result
        
        from jarvis.policy.approval import ApprovalDecision
        mock_approval = MagicMock()
        mock_resp = MagicMock()
        mock_resp.decision = ApprovalDecision.ALLOW_SESSION
        mock_resp.expires_at = None
        mock_approval.request_approval.return_value = mock_resp
        
        ctrl = JarvisController(agent_backend=agent, policy_engine=mock_policy, approval_handler=mock_approval)
        ctrl.register_tool('test_tool', lambda **k: "executed tool")
        
        # First request should call request_approval
        ctrl.process_request('run test')
        mock_approval.request_approval.assert_called_once()
        
        # Second request with exact same args should use cache
        mock_approval.request_approval.reset_mock()
        ctrl.process_request('run test')
        mock_approval.request_approval.assert_not_called()
        
    def test_controller_audit_failure_closes(self):
        agent = self._make_mock_agent()
        mock_audit = MagicMock()
        mock_audit.log_event.side_effect = Exception("DB Disk Full")
        
        ctrl = JarvisController(agent_backend=agent, audit_logger=mock_audit)
        
        with self.assertRaisesRegex(RuntimeError, "Audit failure"):
            ctrl.process_request('run test')
if __name__ == '__main__':
    unittest.main()
