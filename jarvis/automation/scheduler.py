"""Automation Scheduler (G25.4).

Manages job scheduling, trigger evaluation, and dispatches authorized jobs
to the JarvisController. The scheduler never executes tools directly.

Execution pipeline per trigger:
  Trigger → Job lookup → Integrity → Authorization → Expiration → Policy → Controller
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from jarvis.automation.models import AutomationJob, JobStatus, TriggerType
from jarvis.automation.authorization import AuthorizationStore, AutomationAuthorization


class ExecutionStatus(Enum):
    """Status of a single job execution."""
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


@dataclass
class ExecutionRecord:
    """Record of a single job execution attempt."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    job_version: int = 0
    authorization_id: str = ""
    trigger_type: str = ""
    scheduled_time: float = 0.0
    actual_start: float = 0.0
    actual_end: float = 0.0
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


class JobStore:
    """In-memory store for automation jobs.

    Will be backed by SQLite in G25.7.
    """

    def __init__(self):
        self._jobs: Dict[str, AutomationJob] = {}

    def add(self, job: AutomationJob) -> None:
        """Add or update a job in the store."""
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Optional[AutomationJob]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    def remove(self, job_id: str) -> bool:
        """Remove a job from the store."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def list_enabled(self) -> List[AutomationJob]:
        """List all enabled, non-expired jobs."""
        return [j for j in self._jobs.values() if j.is_runnable()]

    def list_all(self) -> List[AutomationJob]:
        """List all jobs regardless of status."""
        return list(self._jobs.values())


class AutomationScheduler:
    """Scheduler for automation jobs.

    Evaluates schedule triggers and dispatches authorized jobs.
    Never executes tools directly — always goes through the executor callback.
    """

    def __init__(self,
                 job_store: JobStore,
                 auth_store: AuthorizationStore,
                 executor: Callable[[AutomationJob, AutomationAuthorization, ExecutionRecord], None],
                 policy_check: Optional[Callable[[AutomationJob], bool]] = None,
                 max_concurrent: int = 5):
        self.job_store = job_store
        self.auth_store = auth_store
        self._executor = executor
        self._policy_check = policy_check
        self._max_concurrent = max_concurrent

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 1.0  # seconds between scheduler ticks
        self._execution_history: List[ExecutionRecord] = []
        self._active_executions: Dict[str, ExecutionRecord] = {}  # job_id -> record
        self._last_run_times: Dict[str, float] = {}  # job_id -> last run timestamp
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the scheduler loop in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run_loop(self) -> None:
        """Main scheduler loop. Evaluates triggers every tick."""
        while self._running:
            self._tick()
            time.sleep(self._tick_interval)

    def _tick(self) -> None:
        """Evaluate all enabled jobs and dispatch those whose triggers fire."""
        with self._lock:
            for job in self.job_store.list_enabled():
                if self._should_fire(job):
                    self._dispatch(job)

    def _should_fire(self, job: AutomationJob) -> bool:
        """Check if a scheduled job's trigger should fire now."""
        if job.trigger_type != TriggerType.SCHEDULE:
            return False
        if job.schedule is None:
            return False

        last_run = self._last_run_times.get(job.job_id, 0.0)
        now = time.time()

        # Check cooldown
        if job.cooldown_seconds > 0 and (now - last_run) < job.cooldown_seconds:
            return False

        # Check schedule interval
        if (now - last_run) >= job.schedule.interval_seconds:
            return True

        return False

    def _dispatch(self, job: AutomationJob) -> None:
        """Dispatch a job for execution through the full verification pipeline."""
        now = time.time()

        # 1. Concurrency check
        if job.job_id in self._active_executions:
            if job.concurrency_policy.value == "skip_if_running":
                return
            # queue_one: skip for now (simplification; real impl would queue)
            return

        # 2. Max concurrent check
        if len(self._active_executions) >= self._max_concurrent:
            return

        # 3. Authorization verification
        auth = self.auth_store.get_authorization_for_job(job)
        if auth is None:
            # No valid authorization — cannot execute (Invariant U)
            return

        # 4. Policy check (if configured)
        if self._policy_check and not self._policy_check(job):
            return

        # 5. Create execution record
        record = ExecutionRecord(
            job_id=job.job_id,
            job_version=job.version,
            authorization_id=auth.authorization_id,
            trigger_type=job.trigger_type.value,
            scheduled_time=now,
            actual_start=now,
            status=ExecutionStatus.STARTED,
        )

        self._active_executions[job.job_id] = record
        self._last_run_times[job.job_id] = now

        # 6. Execute (via callback — never directly)
        try:
            self._executor(job, auth, record)
            record.status = ExecutionStatus.COMPLETED
            record.actual_end = time.time()
            job.record_run()
            auth.record_run()
        except Exception as e:
            record.status = ExecutionStatus.FAILED
            record.error = str(e)
            record.actual_end = time.time()
        finally:
            self._execution_history.append(record)
            if job.job_id in self._active_executions:
                del self._active_executions[job.job_id]

    def trigger_manual(self, job_id: str) -> Optional[ExecutionRecord]:
        """Manually trigger a specific job (outside of the schedule loop)."""
        with self._lock:
            job = self.job_store.get(job_id)
            if job is None or not job.is_runnable():
                return None
            self._dispatch(job)
            if self._execution_history:
                return self._execution_history[-1]
            return None

    def get_execution_history(self, job_id: Optional[str] = None) -> List[ExecutionRecord]:
        """Retrieve execution history, optionally filtered by job_id."""
        if job_id:
            return [r for r in self._execution_history if r.job_id == job_id]
        return list(self._execution_history)
