"""Crash recovery for automation (G25.9).

After a crash/restart, the scheduler must:
1. Load persisted job state
2. Verify integrity of each job
3. Reconcile any in-progress executions
4. Apply duplicate-execution rules
5. Resume only authorized, valid jobs

For executions in UNKNOWN state, the default is: do NOT automatically
replay a potentially non-idempotent mutation.
"""
from enum import Enum
from typing import List, Optional

from jarvis.automation.models import AutomationJob
from jarvis.automation.scheduler import ExecutionRecord, ExecutionStatus, JobStore
from jarvis.automation.authorization import AuthorizationStore


class RecoveryAction(Enum):
    """What the recovery system decides for an incomplete execution."""
    SKIP = "skip"           # do not replay
    RETRY = "retry"         # safe to retry (read-only)
    MANUAL = "manual"       # requires operator decision


class RecoveryResult:
    """Result of recovering a single incomplete execution."""
    def __init__(self, record: ExecutionRecord, action: RecoveryAction, reason: str):
        self.record = record
        self.action = action
        self.reason = reason


class CrashRecovery:
    """Handles recovery after scheduler restart.

    Default behavior: non-idempotent mutations are NOT replayed.
    Read-only jobs may be retried.
    """

    def __init__(self, job_store: JobStore, auth_store: AuthorizationStore,
                 safe_capabilities: Optional[set] = None):
        self.job_store = job_store
        self.auth_store = auth_store
        # Capabilities known to be safe for automatic retry (read-only)
        self._safe_capabilities = safe_capabilities or set()

    def recover(self, incomplete_records: List[ExecutionRecord]) -> List[RecoveryResult]:
        """Evaluate incomplete execution records and decide recovery action.

        For each record in STARTED or UNKNOWN state:
        - If the job's capability is in the safe set → RETRY
        - Otherwise → SKIP (do not replay)
        """
        results = []
        for record in incomplete_records:
            if record.status not in (ExecutionStatus.STARTED, ExecutionStatus.UNKNOWN):
                continue

            job = self.job_store.get(record.job_id)
            if job is None:
                results.append(RecoveryResult(
                    record, RecoveryAction.SKIP, "Job no longer exists"
                ))
                continue

            # Verify authorization still valid
            auth = self.auth_store.get_authorization_for_job(job)
            if auth is None:
                results.append(RecoveryResult(
                    record, RecoveryAction.SKIP, "Authorization no longer valid"
                ))
                continue

            # Safe capabilities can be retried
            if job.capability in self._safe_capabilities:
                results.append(RecoveryResult(
                    record, RecoveryAction.RETRY,
                    f"Safe capability {job.capability} — automatic retry"
                ))
            else:
                # Default: do NOT replay mutations
                results.append(RecoveryResult(
                    record, RecoveryAction.SKIP,
                    f"Non-idempotent capability {job.capability} — skipping"
                ))

        return results
