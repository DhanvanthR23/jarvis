"""Event trigger system (G25.12).

Events are untrusted input (Invariant Z). An event only selects a job —
it cannot modify capability, arguments, authorization, or privilege.
"""
import uuid
from dataclasses import dataclass, field


@dataclass
class EventDefinition:
    """Declarative event definition. No arbitrary code."""
    source: str         # e.g. "system", "network", "disk"
    condition: str      # e.g. "disk_usage > 90"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Event:
    """An actual event occurrence (untrusted input)."""
    source: str
    condition: str
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ConditionEvaluator:
    """Evaluates declarative conditions against event payloads.

    Only supports a restricted set of operators. No eval(), no exec(),
    no arbitrary Python expressions.
    """

    OPERATORS = {
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
    }

    def evaluate(self, condition: str, payload: dict) -> bool:
        """Evaluate a condition string against a payload.

        Supports: "field op value" format only.
        Example: "disk_usage > 90"
        """
        parts = condition.split()
        if len(parts) != 3:
            return False

        field_name, op, value_str = parts

        if op not in self.OPERATORS:
            return False

        actual = payload.get(field_name)
        if actual is None:
            return False

        try:
            expected = type(actual)(value_str)
        except (ValueError, TypeError):
            return False

        return self.OPERATORS[op](actual, expected)


class EventRouter:
    """Routes events to matching automation jobs.

    An event selects a job. It cannot modify the job's capability or arguments.
    """

    def __init__(self):
        self._bindings: dict[str, str] = {}  # event_def_id -> job_id
        self._evaluator = ConditionEvaluator()

    def bind(self, event_def: EventDefinition, job_id: str) -> None:
        """Bind an event definition to a job."""
        self._bindings[event_def.event_id] = job_id

    def unbind(self, event_def_id: str) -> None:
        """Remove an event binding."""
        self._bindings.pop(event_def_id, None)

    def route(self, event: Event, event_defs: list[EventDefinition]) -> list[str]:
        """Route an event to matching job IDs.

        Returns list of job_ids whose event definitions match.
        The event payload is checked against the condition but NEVER
        used to modify the job's arguments.
        """
        matched_jobs = []
        for edef in event_defs:
            if edef.source != event.source:
                continue
            if not self._evaluator.evaluate(edef.condition, event.payload):
                continue
            job_id = self._bindings.get(edef.event_id)
            if job_id:
                matched_jobs.append(job_id)
        return matched_jobs
