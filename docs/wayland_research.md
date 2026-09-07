# Niri Wayland Automation & AI Agent Research

This document outlines how an AI agent can automate interactions within the **Niri** Wayland compositor (a scrollable-tiling compositor built on Smithay), explicitly avoiding legacy X11 techniques and favoring semantic APIs.

## 1. Window Discovery & State Management (Niri IPC)
Under Wayland, global window listing is restricted for security. However, Niri provides a robust, native IPC mechanism for discovery:
* **`niri msg --json windows`**: Returns a machine-readable JSON array of all active windows, including their `id`, `app-id`, `title`, and states (focused, workspace, etc.).
* **Event Stream**: Agents can subscribe to `niri msg event-stream` to receive real-time push notifications about window creations, deletions, and focus changes, avoiding the overhead of continuous polling.
* **Direct Socket**: For tighter integration, AI agents can communicate directly with the UNIX domain socket located at `$NIRI_SOCKET`, sending JSON payloads to actuate windows (e.g., `focus-window`, `close-window`).

## 2. Input Injection (Keyboard & Mouse)
Wayland's security model strictly prohibits arbitrary clients from injecting input into other windows (rendering tools like `xdotool` obsolete). The following solutions are viable for Niri:
* **libei (Emulated Input)**: The modern, standardized, and secure API for input emulation via XDG Desktop Portals. This is the recommended long-term target for AI agents, as it negotiates input permissions properly with the compositor.
* **wtype**: A standard Wayland text and keyboard injection tool.
* **wlr-virtual-pointer**: Although Niri is based on Smithay (not wlroots), it explicitly implements the `wlr-virtual-pointer-unstable-v1` protocol. Tools like `wlrctl` or a custom Wayland client can use this protocol to synthesize accurate mouse movements and clicks.
* **ydotool (Kernel-level)**: If Wayland security boundaries obstruct the agent, `ydotool` bypasses the compositor entirely by writing directly to `/dev/uinput`. This requires root/`udev` permissions and a background daemon (`ydotoold`), but offers guaranteed unhindered global input.

## 3. Screenshots & Vision
For computer vision tasks, Niri fully supports standard Wayland capture protocols:
* **grim & slurp**: The standard Wayland combination. `grim` extracts screen buffers, and `slurp` provides region selection if needed. The output can be piped directly to an AI agent's vision model.
* **Built-in / niri-shot**: Niri has native screenshot capabilities. Agents can trigger full-screen, window, or region captures programmatically via IPC (`niri msg action screenshot ...`). Setting `screenshot-path null` in the Niri config allows scripts to handle the output buffer directly without saving to disk.

## 4. Semantic / Accessibility Interfaces (AT-SPI & D-Bus)
To parse GUI structures without relying purely on OCR/Vision, agents should leverage the **Accessibility Toolkit Service Provider Interface (AT-SPI2)** over D-Bus:
* **The Accessibility Bus**: UI toolkits (GTK, Qt, Electron via specific flags) expose a DOM-like semantic tree of the application (buttons, menus, text fields, checkboxes) to the D-Bus accessibility session.
* **Reading the Tree**: An AI agent can use libraries like `pyatspi2` to traverse this tree, extracting labels, roles, and states. 
* **Wayland Limitations**: Because Wayland does not have a concept of global coordinates for isolated windows, the bounding boxes returned by AT-SPI are relative to the window. To interact with an element (e.g., clicking it), the agent must query the window's global position via Niri IPC (`niri msg --json windows`) and offset the AT-SPI local coordinates accordingly.
