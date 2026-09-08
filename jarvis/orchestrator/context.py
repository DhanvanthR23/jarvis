"""Context and causality tracking for multi-agent architecture (G26).

Manages trace_id, span_id, and parent_span_id for distributed execution.
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionContext:
    """Represents the execution context of a specific agent turn."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    agent_id: str
    agent_role: str

    @classmethod
    def create_root(cls, agent_id: str, agent_role: str) -> "ExecutionContext":
        """Create a new root execution context (no parent)."""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            agent_id=agent_id,
            agent_role=agent_role,
        )

    def create_child(self, agent_id: str, agent_role: str) -> "ExecutionContext":
        """Create a child execution context (delegated turn)."""
        return ExecutionContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            agent_id=agent_id,
            agent_role=agent_role,
        )
