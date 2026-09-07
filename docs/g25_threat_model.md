# G25 Automation: Threat Model & Invariants

## Core Principle
> **Automation is an independently authorized execution context. Interactive approval from the user must never silently become standing authorization for future automated actions.**

## Invariants

### U — Automation has no implicit authorization
A previous interactive approval does not automatically authorize future automated executions.
Interactive approval ≠ Standing automation permission.
Every automated job must have an explicit automation authorization record.

### V — Automation jobs are capability-bound
An automation definition must identify exactly what it is permitted to invoke.
It must never mean "run whatever AGY decides".

### W — Automation cannot expand authority dynamically
An automation job cannot silently change capability, arguments, targets, privilege level,
schedule, network scope, or filesystem scope during execution.
Changes require a new authorization state (new job version).

### X — Automation fails closed
If any required component is invalid (job definition, authorization, manifest hash,
policy, scheduler state, sandbox, audit), the automation must not execute.

### Y — Automation is independently auditable
Every scheduled execution gets a complete audit chain containing:
job_id, job_version, trigger, scheduled_time, actual_start, capability,
canonical_arguments_hash, authorization_id, policy_decision, execution_result, timestamp.
Automation must be distinguishable from interactive execution.

### Z — External triggers are untrusted input
An event (webhook, filesystem event, network event, timer payload) is data, not authorization.
An event cannot itself grant a capability.

## Trust Boundaries
### Trusted
- Automation Scheduler
- Job Store
- Automation Policy
- Jarvis Controller
- Policy Engine
- Approval infrastructure
- Audit
- Output Security Filter

### Untrusted
- AGY
- AGY-generated plans
- AGY-generated job parameters unless validated
- External event payloads
