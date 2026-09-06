from jarvis.agent.interface import AgentBackend
from typing import Callable

class AGYBackend(AgentBackend):
    def __init__(self):
        raise NotImplementedError("AGY backend requires G15+ and explicit authorization")
        
    def process(self, user_input: str, tool_callback: Callable[[str, dict], dict]) -> str:
        raise NotImplementedError("AGY backend requires G15+ and explicit authorization")
