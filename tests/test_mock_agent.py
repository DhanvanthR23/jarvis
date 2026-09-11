import unittest

from jarvis.agent.mock import DEFAULT_SCENARIOS, MockAgent, ScriptedScenario, ScriptedStep


class TestMockAgent(unittest.TestCase):
    def setUp(self):
        self.agent = MockAgent(DEFAULT_SCENARIOS)
        
    def test_matches_scenario_by_trigger_substring(self):
        def dummy_cb(tool, args): return "ok"
        response = self.agent.process("check my disk space", dummy_cb)
        self.assertIn("Disk usage", response)
        
    def test_calls_tool_callback(self):
        calls = []
        def track_cb(tool, args):
            calls.append(tool)
            return f"result_for_{tool}"
            
        self.agent.process("wifi is broken", track_cb)
        self.assertEqual(calls, ["network_interfaces", "network_status"])
        
    def test_returns_scenario_response(self):
        def dummy_cb(tool, args): return "OK"
        response = self.agent.process("show process list", dummy_cb)
        self.assertEqual(response, "Running processes: OK")
        
    def test_default_response(self):
        def dummy_cb(tool, args): return "OK"
        response = self.agent.process("unknown command here", dummy_cb)
        self.assertEqual(response, "I don't know how to help with that.")
        
    def test_handles_multiple_scenarios(self):
        def dummy_cb(tool, args): return "OK"
        resp1 = self.agent.process("wifi", dummy_cb)
        resp2 = self.agent.process("disk", dummy_cb)
        self.assertIn("Wifi", resp1)
        self.assertIn("Disk", resp2)
        
    def test_dataclasses_valid(self):
        step = ScriptedStep("tool", {"a": 1})
        scenario = ScriptedScenario("trig", [step], "resp")
        self.assertEqual(step.tool_name, "tool")
        self.assertEqual(scenario.trigger, "trig")

if __name__ == '__main__':
    unittest.main()
