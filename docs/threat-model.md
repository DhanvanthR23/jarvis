# Jarvis Threat Model

## 1. Component Trust Boundaries

### What can AGY access?
- Its own sandbox workspace (`/home/agent/workspace`) — read/write
- Jarvis MCP server via Unix domain socket (`/run/jarvis/mcp.sock`) — request/response only
- Minimal read-only system directories (`/usr`, minimal `/etc`, `/proc` isolated, minimal `/dev`)
- Private `/tmp`

### What can AGY NOT access?
- Host home directory, `~/.ssh`, `~/.gnupg`, `~/.config`, browser profiles
- `audit.db`, `anchor.log`, `capabilities.toml`, trusted manifest hash
- Jarvis credentials, API keys, cloud credentials, GitHub tokens
- Host process table (PID namespace isolation)
- IP networking (network namespace isolation)
- Any file outside the sandbox except via MCP tools

### What can Jarvis access?
- Full host filesystem (it is the trusted controller)
- `audit.db` (read/write)
- `anchor.log` (append)
- `capabilities.toml` (read, integrity-verified)
- Credentials store
- Unix domain socket (listen)

### What can tools access?
- Only what Jarvis delegates after policy approval
- Tools execute on the host, outside the sandbox
- Each tool has a defined capability with a risk tier

### What requires approval?
- `files.write()` — user configuration changes
- `service.restart()` — service state changes
- `package.install()` — system modification
- Memory writes from agent inference (not explicit user statements)
- Any capability marked `approval` in `capabilities.toml`

### What is permanently forbidden?
- `arbitrary_shell` — unrestricted shell execution
- `sudo` — privilege escalation
- Any unsandboxed AGY execution
- AGY access to audit/anchor/manifest/credentials
- Permanent unrestricted authorization grants

### Where are secrets?
- Host environment variables (never inherited by sandbox)
- `~/.ssh/`, `~/.gnupg/`, `~/.config/` (never mounted into sandbox)
- Jarvis credentials store (host-side only, never exposed to AGY)
- `capabilities.toml` trusted hash (host-side only)

### What happens when components crash?
- **AGY crash**: Jarvis detects unexpected exit, logs audit event, reports to user. No retry without policy check.
- **Jarvis crash**: AGY loses MCP socket, cannot proceed. No tool calls possible.
- **Tool crash**: Jarvis catches exception, logs failure in audit, returns error to AGY via MCP.
- **MCP crash**: AGY loses communication, Jarvis logs event.
- **Audit DB corruption**: Jarvis refuses to start until integrity is verified.

### What happens when policy becomes inconsistent?
- Startup: manifest hash mismatch → startup halted
- Runtime: unknown capability requested → DENY (default-deny)
- Conflicting rules: most restrictive wins

### What happens when sandbox creation fails?
- Jarvis refuses to launch AGY — fail-closed, no fallback
- Preflight failure, namespace failure, mount failure, verification failure → all result in "AGY execution refused"

---

## 2. Threat Catalog

### T1 — AGY reads secrets
**Threat**: AGY attempts to read SSH keys, API tokens, cloud credentials from host filesystem.
**Control**: Sandbox does not mount host home directory. Environment is constructed minimally (HOME=/home/agent). No credential inheritance.

### T2 — AGY accesses host filesystem
**Threat**: AGY reads/writes arbitrary host files outside its workspace.
**Control**: Sandbox filesystem is constructed with explicit bind mounts only. Host paths not mounted are inaccessible. `/usr`, `/etc` are read-only.

### T3 — AGY escapes sandbox
**Threat**: AGY exploits a vulnerability to break out of bubblewrap isolation.
**Control**: User namespaces, PID namespaces, mount namespaces, network namespaces. Defense in depth: even if sandbox is escaped, MCP policy engine still gates all tool access. Sandbox verification step confirms isolation before AGY starts.

### T4 — AGY bypasses MCP
**Threat**: AGY communicates with host services directly, bypassing the MCP policy layer.
**Control**: No IP networking in sandbox. Only communication channel is the Unix domain socket to Jarvis MCP. AGY cannot reach host services.

### T5 — Policy bug
**Threat**: A bug in the policy engine allows a tool call that should be denied.
**Control**: Default-deny policy. Capability manifest is integrity-verified. Policy engine is centralized — no tool defines its own authorization. Comprehensive policy tests.

### T6 — Tool bug
**Threat**: A tool implementation has a vulnerability (path traversal, injection, etc.).
**Control**: Tools receive structured arguments, not raw shell commands. Path arguments are validated/canonicalized. Tools are separate from policy — even a buggy tool is only reachable after policy approval.

### T7 — Memory poisoning
**Threat**: AGY writes misleading information to Jarvis memory to influence future behavior.
**Control**: Memory writes are a capability gated by the policy engine. Agent-inferred memories go to pending review. High-impact memories require explicit user approval. Provenance tracked on every entry.

### T8 — Audit tampering
**Threat**: AGY or a compromised component modifies or deletes audit records.
**Control**: AGY has zero access to audit.db and anchor.log. Hash chain provides tamper evidence. External anchor (append-only file) provides independent verification. Anchor is inaccessible to AGY.

### T9 — Sandbox regression
**Threat**: A code change inadvertently weakens sandbox isolation.
**Control**: Version-controlled sandbox test fixtures. Security suite runs on any security-sensitive change. Security tests are authoritative — never removed, skipped, weakened, or xfailed. Invariant failure freezes capability expansion.

### T10 — Manifest tampering
**Threat**: capabilities.toml is modified to grant unauthorized capabilities.
**Control**: Manifest is hashed at startup and compared to trusted reference hash. Mismatch halts startup. Manifest changes are audited events. AGY cannot access the manifest file.

### T11 — Approval fatigue
**Threat**: User rubber-stamps approvals due to excessive prompts, allowing harmful actions.
**Control**: Risk tiers minimize approval prompts for safe operations. Only genuinely risky operations require approval. Structured approval requests show clear context (actor, capability, target, risk). No permanent unrestricted authorization.

### T12 — Transport interception
**Threat**: Another process on the host intercepts Unix domain socket traffic.
**Control**: Socket permissions restrict access. Socket is bind-mounted into sandbox at a controlled path. Only Jarvis listens on the socket.

---

## 3. Security Invariants

| ID | Invariant | Violation Response |
|----|-----------|-------------------|
| A | AGY is untrusted | Architectural — enforced by design |
| B | AGY never runs unsandboxed | Fail-closed launcher; no fallback path |
| C | Sandbox failure is fail-closed | Preflight/verify fail → AGY refused |
| D | OS containment and MCP policy are separate defenses | Neither substitutes the other |
| E | MCP via Unix socket only | No TCP, no IP networking for AGY |
| F | Capability manifest is integrity-verified | Hash mismatch → startup halt |
| G | Every capability invocation is policy-checked | AGY → MCP → Policy → Tool, always |
| H | Memory is a capability | Writes go through policy engine |
| I | Audit evidence outside AGY's reach | Zero access to audit.db, anchor.log, capabilities.toml |
| J | Audit chain has external anchor | Hash chain + append-only anchor file |
| K | Security invariant failure freezes capability expansion | Fix + pass security suite before new work |
