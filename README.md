# Jarvis

> **Jarvis is now fully functional and operational locally!**

Jarvis is a secure, multi-agent orchestration architecture designed to run untrusted agent backends (like AGY) in isolated sandboxes while maintaining strict security policies and audit trails.

## Core Features

- **Multi-Agent Orchestration (G26)**: Hub-and-spoke architecture where specialized agents (e.g., orchestrator, system diagnostics, system maintenance, browser research) run in completely isolated sandboxes with zero direct agent-to-agent IPC.
- **Strict Sandboxing**: Utilizes `bwrap` (Bubblewrap) to enforce strong isolation. Agents have no host credentials, no IP networking, and minimal read-only filesystems.
- **Policy Engine**: Role-based access control (RBAC) enforced by a verified `capabilities.toml` manifest. Tools are gated by risk tiers (`safe`, `approval`, `disabled`).
- **Audit Logging & Tracing**: Distributed execution tracing (trace, span, parent span) backed by an immutable SQLite audit log and external anchor.
- **Output Security Filter**: Scans all inter-agent messages and user-facing output for secrets (e.g., AWS keys, GitHub tokens) to prevent leaks.
- **Automation Pipeline (G25)**: Supports running capability-bound background jobs with explicit authorization separation from interactive sessions.
- **Local Voice Interface (G27)**: High-accuracy, entirely local Speech-to-Text and Text-to-Speech using `faster-whisper` and `Kokoro ONNX` with conversational text sanitization.

## Architecture

The system centers around the `JarvisController` which coordinates:
1. **Agent Sandbox**: The isolated environment running the LLM backend.
2. **MCP Server**: The socket bridge over which tools are invoked.
3. **Policy Engine**: Verifies if the active role is permitted to run the requested tool.
4. **Approval Cache**: Prompts the user for confirmation on mutating actions.
5. **Audit Logger**: Cryptographically chains execution events.

## Usage

To start the interactive REPL:
```bash
# Start the Jarvis CLI
./jarvis.sh
```

To run an interactive Voice Session:
```bash
./jarvis.sh --voice --voice-engine=faster-whisper
```

To run a one-shot query:
```bash
./jarvis.sh diagnose my wifi
```

To use a specific backend (mock or agy):
```bash
./jarvis.sh --backend agy
```

## Security Invariants
The security model is defined by strict invariants (A-AF) documented in `jarvis/security/invariants.py`. The primary rule is that the Agent is untrusted and all data leaving or entering the sandbox must be validated by the host controller.
