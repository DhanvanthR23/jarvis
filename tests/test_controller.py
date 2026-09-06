"""Tests for Jarvis controller (G6)."""

import unittest
from unittest.mock import MagicMock

from jarvis.core.controller import JarvisController
from jarvis.core.events import EventType
from jarvis.agent.mock import MockAgent, ScriptedScenario, ScriptedStep


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


if __name__ == '__main__':
    unittest.main()
