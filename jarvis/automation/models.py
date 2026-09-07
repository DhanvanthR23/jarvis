"""Automation job model (G25.2).

Defines the core data structures for automation jobs. A job describes:
When → what exact capability → with what exact arguments → under what authorization.

Jobs are immutably versioned: changing any security-relevant field creates a new
version. An old authorization must not automatically authorize a modified job.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TriggerType(Enum):
    """Types of triggers that can fire a job."""
    SCHEDULE = "schedule"
    EVENT = "event"
    MANUAL = "manual"


class JobStatus(Enum):
    """Lifecycle status of a job."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ConcurrencyPolicy(Enum):
    """What to do if a job is triggered while already running."""
    SKIP_IF_RUNNING = "skip_if_running"
    QUEUE_ONE = "queue_one"


@dataclass(frozen=True)
class ScheduleTrigger:
    """A cron-like schedule trigger.

    Uses a simplified interval model for now; can be extended to full cron later.
    """
    interval_seconds: int
    start_at: Optional[float] = None  # absolute timestamp; None = now


@dataclass(frozen=True)
class EventTrigger:
    """A declarative event trigger.

    Source and condition are validated strings, not arbitrary code.
    """
    source: str        # e.g. "system"
    condition: str     # e.g. "disk_usage > 90"


@dataclass
class AutomationJob:
    """An automation job definition.

    Immutably versioned: changing any security-relevant field bumps the version.
    The job_id stays the same; the version changes.
    """
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    name: str = ""

    # What to do
    capability: str = ""
    arguments: dict = field(default_factory=dict)

    # When to do it
    trigger_type: TriggerType = TriggerType.SCHEDULE
    schedule: Optional[ScheduleTrigger] = None
    event: Optional[EventTrigger] = None

    # Lifecycle
    status: JobStatus = JobStatus.ENABLED
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # None = must be set explicitly

    # Execution limits
    max_runs: Optional[int] = None
    run_count: int = 0
    cooldown_seconds: int = 0
    max_runtime_seconds: int = 300  # 5 minutes default
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.SKIP_IF_RUNNING

    def compute_hash(self) -> str:
        """Compute a deterministic hash of the security-relevant fields.

        This hash is used to bind authorizations to exact job definitions.
        If any of these fields change, the hash changes, and re-authorization
        is required.
        """
        payload = json.dumps({
            "job_id": self.job_id,
            "version": self.version,
            "capability": self.capability,
            "arguments": self.arguments,
            "trigger_type": self.trigger_type.value,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def is_expired(self) -> bool:
        """Check if the job has exceeded its expiration timestamp."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def is_runnable(self) -> bool:
        """Check if the job is in a state where it can execute."""
        if self.status != JobStatus.ENABLED:
            return False
        if self.is_expired():
            return False
        if self.max_runs is not None and self.run_count >= self.max_runs:
            return False
        return True

    def record_run(self) -> None:
        """Increment the run counter."""
        self.run_count += 1

    def create_new_version(self, **changes) -> 'AutomationJob':
        """Create a new version of this job with the specified changes.

        The job_id stays the same; the version is bumped. The new version
        has no authorization until explicitly re-authorized.
        """
        current = {
            "job_id": self.job_id,
            "version": self.version + 1,
            "name": self.name,
            "capability": self.capability,
            "arguments": dict(self.arguments),
            "trigger_type": self.trigger_type,
            "schedule": self.schedule,
            "event": self.event,
            "status": JobStatus.ENABLED,
            "created_at": time.time(),
            "expires_at": self.expires_at,
            "max_runs": self.max_runs,
            "run_count": 0,
            "cooldown_seconds": self.cooldown_seconds,
            "max_runtime_seconds": self.max_runtime_seconds,
            "concurrency_policy": self.concurrency_policy,
        }
        current.update(changes)
        return AutomationJob(**current)
