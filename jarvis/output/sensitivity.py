"""Sensitivity metadata for tool results (plan2.md section 13, primary layer).

Tool results carry provenance/sensitivity tags so the OutputSecurityFilter
knows what must never reach a presentation channel.
"""
from dataclasses import dataclass
from enum import Enum, auto


class SensitivityLevel(Enum):
    """How sensitive a piece of tool output is."""
    PUBLIC = auto()        # safe for any channel
    INTERNAL = auto()      # safe for CLI, blocked from TTS/GUI without review
    SECRET = auto()        # blocked from all presentation channels
    RESTRICTED = auto()    # blocked; existence should not be disclosed


@dataclass
class SensitivityTag:
    """Provenance/sensitivity metadata attached to a tool result."""
    level: SensitivityLevel
    source_tool: str = ''
    source_capability: str = ''
    reason: str = ''
