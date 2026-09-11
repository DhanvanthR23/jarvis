"""Automation authorization model (G25.3).

An automation authorization is a separate, explicit grant that binds:
- a specific job_id + version
- a specific capability + arguments (via hash)
- a specific trigger type
- a lifetime (expiration)
- an optional run limit

Interactive approvals (ALLOW_ONCE, ALLOW_SESSION) never create automation
authorizations. Only explicit automation authorization creation does.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field

from jarvis.automation.models import AutomationJob


@dataclass
class AutomationAuthorization:
    """Explicit authorization for a specific automation job version."""
    authorization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    job_version: int = 0
    job_hash: str = ""  # hash of the job's security-relevant fields

    capability: str = ""
    argument_hash: str = ""

    allowed_trigger: str = ""  # e.g. "schedule", "event", "manual"

    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    max_runs: int | None = None
    run_count: int = 0

    enabled: bool = True
    revoked: bool = False

    def is_valid(self) -> bool:
        """Check if authorization is currently valid."""
        if self.revoked:
            return False
        if not self.enabled:
            return False
        if self.expires_at is not None and time.time() > self.expires_at:
            return False
        return not (self.max_runs is not None and self.run_count >= self.max_runs)

    def matches_job(self, job: AutomationJob) -> bool:
        """Verify this authorization matches the given job exactly.

        Checks job_id, version, and the computed hash of security-relevant fields.
        If any of these don't match, the authorization is not valid for this job.
        """
        if self.job_id != job.job_id:
            return False
        if self.job_version != job.version:
            return False
        return self.job_hash == job.compute_hash()

    def record_run(self) -> None:
        """Increment the run counter on this authorization."""
        self.run_count += 1

    def revoke(self) -> None:
        """Permanently revoke this authorization."""
        self.revoked = True

    def disable(self) -> None:
        """Temporarily disable this authorization."""
        self.enabled = False

    def enable(self) -> None:
        """Re-enable a disabled (not revoked) authorization."""
        if not self.revoked:
            self.enabled = True


class AuthorizationStore:
    """In-memory store for automation authorizations.

    Provides lookup, creation, and validation of automation authorizations.
    Will be backed by SQLite in G25.7.
    """

    def __init__(self):
        self._authorizations: dict[str, AutomationAuthorization] = {}

    def create_authorization(self, job: AutomationJob,
                              expires_at: float | None = None,
                              max_runs: int | None = None) -> AutomationAuthorization:
        """Create a new automation authorization for a specific job version.

        This is the ONLY way to authorize an automation job. Interactive
        approvals (ALLOW_ONCE, ALLOW_SESSION) never create these.
        """
        arg_hash = hashlib.sha256(
            json.dumps(job.arguments, sort_keys=True).encode()
        ).hexdigest()

        auth = AutomationAuthorization(
            job_id=job.job_id,
            job_version=job.version,
            job_hash=job.compute_hash(),
            capability=job.capability,
            argument_hash=arg_hash,
            allowed_trigger=job.trigger_type.value,
            expires_at=expires_at,
            max_runs=max_runs,
        )
        self._authorizations[auth.authorization_id] = auth
        return auth

    def get_authorization_for_job(self, job: AutomationJob) -> AutomationAuthorization | None:
        """Find a valid authorization that matches the given job exactly."""
        for auth in self._authorizations.values():
            if auth.matches_job(job) and auth.is_valid():
                return auth
        return None

    def get_by_id(self, authorization_id: str) -> AutomationAuthorization | None:
        """Retrieve an authorization by its ID."""
        return self._authorizations.get(authorization_id)

    def revoke_by_job_id(self, job_id: str) -> int:
        """Revoke all authorizations for a given job_id. Returns count revoked."""
        count = 0
        for auth in self._authorizations.values():
            if auth.job_id == job_id and not auth.revoked:
                auth.revoke()
                count += 1
        return count

    def list_all(self) -> list:
        """Return all authorizations."""
        return list(self._authorizations.values())
