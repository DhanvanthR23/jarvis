from enum import Enum, auto
from dataclasses import dataclass, field
import time
import uuid
from typing import Dict, Any

class EventType(Enum):
    REQUEST = auto()
    TOOL_CALL = auto()
    POLICY_CHECK = auto()
    APPROVAL_REQUEST = auto()
    APPROVAL_RESPONSE = auto()
    TOOL_RESULT = auto()
    AGENT_RESPONSE = auto()
    ERROR = auto()
    SESSION_START = auto()
    SESSION_END = auto()

@dataclass
class Event:
    type: EventType
    session_id: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
