from abc import ABC, abstractmethod
from typing import Callable, Any

class AgentBackend(ABC):
    @abstractmethod
    def process(self, user_input: str, tool_callback: Callable[[str, dict], dict]) -> str:
        """
        Process user input and return a string response.
        
        tool_callback signature: (tool_name: str, args: dict) -> dict
        """
        pass
