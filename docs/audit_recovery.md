# Audit Anchor Recovery and Documentation

The Jarvis project utilizes a cryptographically chained audit log (`jarvis.audit.logger`) anchored to an external, append-only file (`anchor.log`). This mechanism satisfies Invariant J, ensuring that no actor (including compromised agent processes or the Jarvis controller itself) can silently erase or modify historical audit events.

## Mechanism Overview

1.  **Chained SQLite Audit Log:** Every event in `audit.db` is sequentially hashed. The `chain_hash` for an event is computed as:
    `H(timestamp + sequence_number + event_data_hash + previous_chain_hash)`
2.  **External Anchor:** After writing an event, the system immediately writes the `timestamp`, `sequence`, and `chain_hash` to the external `anchor.log`.
3.  **Privilege Boundary (`chattr +a`):** The `anchor.log` resides outside the sandbox (e.g., `/var/log/jarvis/anchor.log`) and is set to append-only at the OS filesystem level using `chattr +a`. This is provisioned via the `scripts/setup_anchor.sh` script (run as root). Because Jarvis runs as a standard user, it cannot remove this append-only flag.

## Verification Procedure

To verify the integrity of the audit log against the external anchor:

1.  **Locate the anchor:** Default is `/var/log/jarvis/anchor.log`.
2.  **Verify Append-Only Status:**
    ```bash
    lsattr /var/log/jarvis/anchor.log
    # Expected output should include 'a', e.g.: -----a--------e---
    ```
3.  **Verify DB Integrity:** The SQLite database `audit.db` (usually found in the project's data directory) should be traversed linearly. For each event `N`, recompute the hash using `event(N-1)`'s hash.
4.  **Match Anchor:** Compare the final `chain_hash` in `audit.db` against the last line of `anchor.log`. If they match, the log is completely intact from sequence 0 up to the present.

## Recovery Procedure

If an audit failure or mismatch occurs, the Jarvis pipeline will automatically "fail-closed" (halt). Follow this procedure to recover:

### Scenario A: Mismatch between `audit.db` and `anchor.log`
This indicates tampering or corruption in the SQLite database.
1.  **Halt Operations:** Do not resume Jarvis.
2.  **Investigate:** Use the anchor log to determine the exact sequence number where the database diverges. Everything before the divergence is verified intact; everything after is suspect.
3.  **Quarantine:** Move `audit.db` and `anchor.log` to a secure quarantine location for forensic analysis.
4.  **Reset:** To resume operations, generate a fresh `audit.db` and establish a new `anchor.log`. **Never blindly overwrite or "fix" the hash mismatch.**

### Scenario B: `anchor.log` Missing or Unwritable
This occurs if the filesystem permissions change or the anchor file is accidentally deleted (which requires root).
1.  Jarvis will instantly raise a `RuntimeError` due to audit failure and refuse to process requests.
2.  Re-run the setup script as root:
    ```bash
    sudo ./scripts/setup_anchor.sh
    ```
3.  Restart the Jarvis daemon. It will automatically detect the highest sequence number in `audit.db` and append the latest hash to the new anchor log, resuming the chain.

### Scenario C: Disk Full / SQLite Corruption
1.  If the host system disk fills up, Jarvis will fail-closed when attempting to append to `audit.db` or `anchor.log`.
2.  Free up disk space.
3.  If `audit.db` was corrupted due to power failure mid-write, you may need to restore from a backup and manually inject a "Restoration Event" anchor into the `anchor.log` indicating the rollback sequence number, before resuming.
