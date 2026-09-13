# G28: Voice, Memory & Dynamic Roles

This document summarizes the recent architectural updates to the Jarvis orchestration pipeline.

## 1. Cloud TTS (edge-tts)
The hardware constraints of the target i3 dual-core CPU prevented the use of high-quality local neural TTS models (like Kokoro and MeloTTS) due to severe latency (~7–15 seconds per sentence). Fast alternatives like Piper TTS suffered from poor vocal quality.

**Architecture Update:**
- A Cloud TTS option was implemented via a host-side proxy daemon (`jarvis/voice/proxy/daemon.py`).
- The daemon uses `edge-tts` to stream high-quality audio back to the Jarvis controller.
- **Zero-Egress Sandbox:** The agent sandbox remains fully isolated from the internet. The agent communicates with the host-side TTS daemon via a Unix socket IPC.
- **Fallback:** If `edge-tts` fails due to network loss, rate limiting, or timeouts, the daemon falls back seamlessly to `piper-tts`.

## 2. Dynamic Role Auto-Switching
Previously, the agent was statically bound to a single role (e.g., `system_diagnostics`) during a session, requiring explicit delegation to access tools in other domains.

**Architecture Update:**
- The `JarvisController` now supports **Dynamic Role Auto-Switching**.
- When an agent calls a tool that is not in its current active role, the controller intercepts the request *before* the policy engine evaluation.
- It scans the `capabilities.toml` manifest for an allowed role containing the tool (e.g., switching from `system_diagnostics` to `browser_research`).
- If found, it temporarily adopts that role. The policy engine still enforces `safe` vs `approval` requirements based on the new role's permissions.

## 3. Persistent Conversational Memory
The `MemoryStore` and `MemoryPolicyEngine` modules have been fully wired into the Jarvis controller.

**Architecture Update:**
- Facts and session preferences are stored in an SQLite database at `~/.jarvis/memory.db`.
- Three tools (`memory_write`, `memory_read`, `memory_search`) have been exposed to the agent.
- These tools are granted to all primary roles, allowing Jarvis to build a persistent context spanning multiple sandbox lifecycles.

## 4. Web Search
A new `browser_search` capability was added, circumventing the need for raw Python Playwright scripts inside the agent. It automatically navigates to DuckDuckGo HTML, parses the top 5 results, and returns clean snippet JSON to the orchestrator, vastly speeding up research queries.
