# Jarvis G20-G23 Research Report

This document compiles the research into implementing the deferred GUI and Browser control capabilities (G20-G23) for Jarvis. The research explicitly targets the **Dell Inspiron 3501 (Intel i3-1005G1, 8GB RAM, Intel Iris Plus Graphics) running CachyOS + Niri**.

---

## Part 1: Isolated GUI (G20-G21)
*Research on letting the agent interact with real GUI apps without seeing the host screen.*

### 1. Options Considered

| Option | Resource Cost | GPU Accel | Sandboxability | Implementation Libraries | Real Hardware Feasibility |
|---|---|---|---|---|---|
| **Xvfb** (X11 Virtual Framebuffer) | Low RAM, High CPU (Software rendering only) | No | Excellent (`bwrap` + X11 socket `DISPLAY=:99`) | `python-xlib`, `xdotool`, `scrot` | Poor. Heavy GUI apps (Electron/Chromium) will spike the dual-core i3 CPU without GPU acceleration. |
| **Xvnc** | Medium RAM, High CPU | No | Good (Requires network isolation or careful port binding) | `python-xlib`, VNC protocols | Worse than Xvfb due to VNC overhead. |
| **Nested Wayland** (`cage`, `wayfire`) | Low RAM, Low CPU | Yes (via `/dev/dri` passthrough) | Good (Requires a host Wayland socket to nest into) | `wtype`, `wlrctl`, `grim`, `pywayland` | Good, but nesting into the host compositor breaks isolation by exposing a window on the host screen. |
| **Headless Wayland** (`sway --headless` or similar wlroots) | Low RAM, Low CPU | Yes (via `/dev/dri` passthrough) | Excellent (Self-contained Wayland socket, no host display) | `wtype`, `wlrctl`, `grim`, `pywayland` | Best. Leverages Intel Iris Plus GPU while remaining completely hidden from the host. |

### 2. Recommended Option
**Headless Wayland (`sway --headless` or a minimal wlroots headless compositor)**
- **Reasoning**: The Intel i3-1005G1 has a weak dual-core CPU but a capable Iris Plus GPU. Software rendering (Xvfb) for modern apps will severely bottleneck the system. A headless wlroots session allows us to bind-mount `/dev/dri/renderD128` into the `bwrap` sandbox, unlocking hardware-accelerated rendering with zero host display output. 
- **Input Isolation**: By utilizing Wayland protocol extensions (`wtype` for keyboard, `wlrctl` or custom PyWayland for mouse, `grim` for screencopy), we avoid exposing `/dev/uinput`. Injecting `/dev/uinput` into the sandbox is a severe security risk as it allows global host input injection.
- **Clean Teardown**: Fits perfectly with `bwrap --die-with-parent`. When the sandbox dies, the headless compositor dies, instantly tearing down the socket and all child GUI processes.

### 3. New Invariants and Capability Manifest Entries
**Manifest Entry Draft**:
- `CAP_ISOLATED_GUI`: True/False. Indicates support for an isolated Wayland compositor socket and virtual input protocol extensions.

**New Invariant Draft**:
> **Invariant (Isolated Input Safety):** Sandboxed GUI execution MUST NOT bind-mount `/dev/input/*` or `/dev/uinput` into the container. All input injection MUST be performed strictly via Wayland protocol extensions directed at the isolated compositor socket.

**Audit Schema Draft**:
Every isolated desktop action must be recorded in the SQLite audit chain (`audit.db`).
- `event_type`: `ISOLATED_GUI_ACTION`
- `metadata`: `{ "session_id": "...", "approval_id": "...", "capability": "desktop_click", "action_args": {"x": 100, "y": 200}, "screenshot_hash": "..." }`

### 4. Rough Gate Breakdown
- **G21.1: Headless Compositor Sandbox Base**: Update `launcher.py` to optionally bind-mount `/dev/dri/renderD128` and initialize `sway --headless` (or equivalent) within the `bwrap` environment.
- **G21.2: Screen Capture Pipeline**: Integrate `grim` into the agent's toolset to capture the headless compositor's output directly from the sandboxed Wayland socket.
- **G21.3: Protocol-Safe Input Injection**: Implement `wtype` (keyboard) and virtual-pointer tooling targeting the sandboxed socket. Validate that `/dev/uinput` is strictly blocked.
- **G21.4: End-to-End GUI Agent Loop**: E2E test verifying the agent can launch an app in the sandbox, take a screenshot, and successfully perform a click/type action without host side-effects.

### 5. Explicit Open Risks / Human Decisions
- **DRM Node Permissions**: Passing `/dev/dri/renderD128` into the sandbox exposes the host kernel's DRM driver to the sandboxed apps. A decision is needed on whether the performance gain of GPU acceleration is worth the slightly increased attack surface on the host kernel.
- **Mouse Interaction Fragmentation**: Keyboard injection is well-supported by `wtype`, but mouse interactions (like dragging) over Wayland protocols can be fragmented. `wlrctl` supports basic clicks, but complex interactions might require writing custom PyWayland bindings.

---

## Part 2: Browser Automation (G23)
*Research on running a headless browser securely within the agent's sandbox.*

### 1. Options Considered & Comparison

| Feature / Tool | Playwright (Python) | Selenium (Python) | Puppeteer (Pyppeteer/pyppeteer2) |
| --- | --- | --- | --- |
| **Resource Cost** | Moderate (Chromium `--headless=new` is efficient, though it still spawns separate browser/renderer/GPU processes) | High (Requires Webdriver daemon + Browser process) | Moderate (Similar browser cost, but async Python wrapper overhead) |
| **Maturity (Python)** | High (Officially supported by Microsoft, excellent async/sync APIs) | Very High (Industry standard, but synchronous and older API design) | Low (Pyppeteer is largely unmaintained; unofficial ports are fragmented) |
| **Sandboxability** | Excellent. Can run system Chromium via `executable_path`. See explicit risks below regarding `--no-sandbox` integration within `bwrap`. | Poor. Needs coordination between webdriver daemon and browser inside the `bwrap` environment, complicating IPC and ports. | Good, but legacy bindings make it hard to confidently tune sandbox flags. |
| **Download/Upload** | First-class event-driven APIs (`expect_download`, `set_input_files`). | Clunky. Requires profile-level download directories and filesystem polling; uploads use `send_keys`. | Supported via CDP, but Python API is poorly documented and brittle. |
| **Hardware Fit (i3/8GB)** | Best fit. Handles GPU-accelerated headless well; low memory overhead if tabs are limited. | Noticeable latency due to driver bridging. | Acceptable, but unmaintained codebase risks memory leaks. |

### 2. Recommended Option
**Playwright (Python)**
- **Reasoning**: It provides a first-class Python binding maintained by Microsoft, significantly reducing the maintenance burden compared to Pyppeteer. Its explicit APIs for handling downloads (`expect_download`) and uploads (`set_input_files`) directly map to G23 capabilities (`browser_download`, `browser_upload`) without requiring polling hacks. Furthermore, Playwright runs Chromium directly without a webdriver intermediary, which minimizes the resource footprint on the i3-1005G1.

### 3. New Invariant(s), Capability Manifest, and Audit Schema
**Capability Manifest Entries (Draft):**
*Note: Due to data exfiltration risks (e.g., agent navigating to `attacker.com/?data=secret`), web navigation is NOT "safe".*
```toml
browser_navigate = "approval"
browser_read = "safe"
browser_type = "approval"
browser_click = "approval"
browser_download = "approval"
browser_upload = "approval"
```

**New Invariants (Draft):**
- **Invariant (Browser Sandbox)**: The browser MUST NEVER construct its own unprivileged user namespace or setuid sandbox. It MUST run with `--no-sandbox` to defer all isolation to the Jarvis `bwrap` boundary.
- **Invariant (File I/O Isolation)**: Browser downloads and uploads MUST strictly target the ephemeral `/home/agent/workspace` bind mount. The browser process MUST NOT have read/write access to the host's native `~/Downloads`.
- **Invariant (Stateful Session Policy)**: `browser_read` is safe-tier ONLY within an active, approved navigation session. The policy engine MUST key off active session state, rather than assuming implicit ordering, to prevent arbitrary unapproved reads.

**Audit Schema Draft**:
To match the rigor of G24/G25, every browser action must be written to the SQLite audit chain (`audit.db`).
- `event_type`: `BROWSER_ACTION`
- `metadata`: `{ "session_id": "...", "approval_id": "...", "capability": "browser_navigate", "url_hash": "...", "target_selector": "..." }`

### 4. Rough Gate Breakdown (G23)
- **G23.1: Browser Headless Integration & Bwrap Verification**: Add Playwright dependency, configure headless execution. Thoroughly audit the nested sandbox overlap (see Open Risks below).
- **G23.2: Safe Web Navigation & Read (Read-Only)**: Implement `browser_navigate`, `browser_read` (DOM extraction/accessibility tree parsing), and `browser_type`. Validate memory usage on the i3 constraint.
- **G23.3: Interactive Actions (Mutations)**: Implement `browser_click`, hooking into the approval flow.
- **G23.4: Data I/O**: Implement `browser_download` and `browser_upload` ensuring file paths are strictly bound to the sandboxed workspace.

### 5. Explicit Open Risks / Human Decisions
- **The `--no-sandbox` Renderer RCE Risk (CRITICAL)**: Passing `--no-sandbox` to Chromium inside Bubblewrap disables Chromium's internal seccomp-bpf and namespace sandbox. If the agent navigates to a malicious site that achieves a renderer RCE, the attacker immediately gains the full privilege of the AGY `bwrap` boundary with no secondary defense. A decision must be made: Can Chromium's internal sandbox coexist with `bwrap` (nested user namespaces), or do we accept the `bwrap` boundary as the sole defense against web-borne RCEs?
- **System Chromium vs. Playwright Binaries**: Should we allow Playwright to download its own browser binaries, or force it to use the host's CachyOS Chromium via `executable_path` (saves space, risks version mismatches)?
- **Memory Limits**: Browsers can easily consume the available 8GB RAM. Do we enforce a hard memory limit (via `bwrap` cgroups or Playwright limits) or rely on agent behavior constraints (e.g. max 1 tab)?

---

## Part 3: Real Wayland Integration (G22)
*Research on allowing the agent to observe and control the actual host desktop under Niri.*

### 1. Options Considered & Comparison

| Approach | Components / Protocols | Resource Cost | Maturity | Sandboxability | Real Hardware Feasibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A: Direct Wayland Protocols** | `wlr-screencopy` (`grim`), `virtual-keyboard-unstable-v1` (`wtype`), `wlr-virtual-pointer-unstable-v1` (`wlrctl`) | **Low** (CLI wrappers invoke directly against Wayland sockets) | High (Standard in wlroots/Smithay) | Medium (Requires Wayland socket access, bypasses user prompts) | **High** (Perfect for low-end i3-1005G1, minimal overhead) |
| **B: Kernel-Level Input** | `uinput` via `ydotool` + `grim` | **Low/Medium** (Background daemon required) | High | Low (`uinput` requires root/input group access, breaking strict sandboxing) | **High** (Universal input, but security risk is extreme) |
| **C: XDG Desktop Portal** | DBus interfaces for ScreenCast/RemoteDesktop | **High** (Often utilizes PipeWire streams, heavier processing) | Medium | **High** (Explicitly designed for sandboxed apps) | **Medium** (PipeWire streams might tax the dual-core i3 more than a simple `grim` loop) |

### 2. Recommended Option
**Option A: Direct Wayland Protocols via CLI Wrappers (`grim`, `wtype`, `wlrctl`)**
- **Reasoning**: Given the strict resource constraints of the Intel i3-1005G1, spinning up PipeWire streams (Option C) for periodic observation is too heavy. Option B (`ydotool`) requires `/dev/uinput` permissions which severely breaks sandboxing and violates the principle of least privilege.
- Option A uses `grim` for lightweight, on-demand framebuffer dumping (which can leverage Intel Iris Plus GPU buffers efficiently) and `wtype`/`wlrctl` for input.
- **The Catch**: Direct protocol access via the Wayland socket allows *silent* observation and control. This requires a robust, explicitly engineered consent/permission model to prevent abuse.

### 3. Permission/Consent Model, Invariants & Audit Schema
This capability introduces a new risk analogous to voice/microphone access (Invariant P). If AGY can silently read the screen, it poses a severe privacy risk.

**Draft New Invariant (Invariant V - Vision / Desktop Access):**
> **Invariant V (Visual Privacy & Desktop Consent):** The agent MUST NOT read the host screen or inject input events without an explicit, verifiable, and visibly indicated user consent state. Screen observation MUST be ephemeral and visually telegraphed to the user (e.g., via a persistent status bar indicator or a mandatory notification when observation begins). The agent CANNOT unilaterally grant itself Wayland socket access or bypass the visual indicator.

**Capability Manifest Entries Required:**
- `CAP_WAYLAND_OBSERVE`: Grants read access to `wlr-screencopy` (via `grim`). Must trigger a visible UI indicator.
- `CAP_WAYLAND_CONTROL`: Grants write access to virtual input protocols. Must be explicitly enabled per-session.

**Audit Schema Draft**:
Every interaction with the real host desktop must be recorded in the SQLite audit chain (`audit.db`).
- `event_type`: `HOST_DESKTOP_ACTION`
- `metadata`: `{ "session_id": "...", "approval_id": "...", "capability": "real_desktop_type", "action_args": {"text": "***"}, "consent_indicator_status": "active" }`

### 4. Rough Gate Breakdown
- **G22.1: Local Observation Sandbox**: Implement a restricted execution wrapper around `grim`. Enforce max screenshot frequency to respect CPU limits. Implement the visual indicator (e.g. `dunst` notification).
- **G22.2: Input Injection Prototyping**: Validate `wtype` (keyboard) and `wlrctl` (pointer) against Niri. Implement a hardware kill-switch to revoke socket access instantly.
- **G22.3: Consent Model Integration**: Wire `CAP_WAYLAND_OBSERVE` and `CAP_WAYLAND_CONTROL` into the agent's lifecycle. Require explicit user prompt to authorize a vision session.
- **G22.4: VLM Pipeline**: Optimize image resizing/compression locally before hitting the LLM API to save bandwidth.

### 5. Explicit Open Risks / Human Decisions
- **Indicator Reliability**: How do we guarantee the visual indicator cannot be suppressed by the agent? (Decision: The indicator should ideally be handled by a separate, hardcoded daemon or compositor plugin that the agent has no write access to).
- **Wayland Socket Isolation**: Giving the agent `$WAYLAND_DISPLAY` gives it full access to the compositor. (Decision: Can we use a proxy like `sommelier` or a Wayland protocol filter to *only* allow screencopy and virtual input, blocking clipboard reads or foreign toplevel management?)
- **Runaway Input Loop**: A hallucinating agent could inject thousands of rapid keystrokes or clicks. (Decision: We must implement rate-limiting on the input wrapper and a hardware-level abort shortcut).
