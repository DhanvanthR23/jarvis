from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jarvis.agent.interface import AgentBackend


@dataclass
class ScriptedStep:
    tool_name: str
    args: dict[str, Any]

@dataclass
class ScriptedScenario:
    trigger: str
    steps: list[ScriptedStep]
    response: str

class MockAgent(AgentBackend):
    def __init__(self, scenarios: list[ScriptedScenario]):
        self.scenarios = scenarios
        
    def process(self, user_input: str, tool_callback: Callable[[str, dict], dict]) -> str:
        input_lower = user_input.lower()
        
        # 1. Find matching scenario
        for scenario in self.scenarios:
            if scenario.trigger.lower() in input_lower:
                results = []
                # 2. Execute each step
                for step in scenario.steps:
                    result = tool_callback(step.tool_name, step.args)
                    results.append(str(result))
                    
                # 3. Return formatted response
                try:
                    return scenario.response.format(*results)
                except Exception:
                    return scenario.response
                    
        # 4. No match
        return "I don't know how to help with that."
        
    @classmethod
    def from_dict(cls, data: dict) -> 'MockAgent':
        scenarios = []
        for s in data.get("scenarios", []):
            steps = [ScriptedStep(**step_data) for step_data in s.get("steps", [])]
            scenarios.append(ScriptedScenario(
                trigger=s["trigger"],
                steps=steps,
                response=s["response"]
            ))
        return cls(scenarios)

DEFAULT_SCENARIOS = [
    ScriptedScenario(
        trigger="wifi",
        steps=[
            ScriptedStep("network_interfaces", {}),
            ScriptedStep("network_status", {"interface": "wlan0"})
        ],
        response="Wifi diagnosis: Interfaces {}, Status {}"
    ),
    ScriptedScenario(
        trigger="disk",
        steps=[
            ScriptedStep("system_info", {})  # Changed from system.disk_usage
        ],
        response="Disk usage information: {}"
    ),
    ScriptedScenario(
        trigger="process",
        steps=[
            ScriptedStep("processes_list", {"limit": 10})
        ],
        response="Running processes: {}"
    )
]
