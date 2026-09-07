"""Wake word integration (plan2.md section 21, G24.14).

Jarvis remains IDLE and deaf until a wake word or hotkey is detected.
"""
import threading
from abc import ABC, abstractmethod
from typing import Callable


class WakeEngine(ABC):
    """Abstract wake trigger (wake word or hotkey)."""

    def __init__(self, on_wake: Callable[[], None]):
        self.on_wake = on_wake
        self._running = False

    @abstractmethod
    def start(self) -> None:
        """Start listening for the wake signal."""
        self._running = True

    @abstractmethod
    def stop(self) -> None:
        """Stop listening."""
        self._running = False


class MockWakeEngine(WakeEngine):
    """Test-only wake engine that can be triggered programmatically."""
    
    def start(self) -> None:
        super().start()

    def stop(self) -> None:
        super().stop()
        
    def trigger(self) -> None:
        if self._running:
            self.on_wake()


class HotkeyWakeEngine(WakeEngine):
    """A simple thread that waits for an Event or CLI input to simulate wake.
    
    In a real deployment, this would hook a global Wayland hotkey or 
    a lightweight continuous listener like Porcupine.
    """
    
    def __init__(self, on_wake: Callable[[], None]):
        super().__init__(on_wake)
        self._thread = None
        self._wake_event = threading.Event()

    def start(self) -> None:
        super().start()
        self._thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        super().stop()
        self._wake_event.set()  # break out of wait

    def trigger(self) -> None:
        self._wake_event.set()

    def _wait_loop(self) -> None:
        while self._running:
            self._wake_event.wait()
            if not self._running:
                break
            self._wake_event.clear()
            self.on_wake()

