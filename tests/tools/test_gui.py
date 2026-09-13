import os
from unittest.mock import patch

import pytest

from jarvis.tools.gui_isolated import (
    desktop_click as isolated_click,
)
from jarvis.tools.gui_isolated import (
    desktop_focus as isolated_focus,
)
from jarvis.tools.gui_isolated import (
    desktop_keypress as isolated_keypress,
)
from jarvis.tools.gui_isolated import (
    desktop_screenshot,
    desktop_windows,
)
from jarvis.tools.gui_isolated import (
    desktop_type as isolated_type,
)
from jarvis.tools.gui_real import (
    desktop_click as real_click,
)
from jarvis.tools.gui_real import (
    desktop_focus as real_focus,
)
from jarvis.tools.gui_real import (
    desktop_keypress as real_keypress,
)
from jarvis.tools.gui_real import (
    desktop_observe,
)
from jarvis.tools.gui_real import (
    desktop_type as real_type,
)


def test_isolated_gui():
    """The isolated GUI interface uses its real Wayland clients."""
    with pytest.raises(NotImplementedError):
        desktop_windows()
    with pytest.raises(NotImplementedError):
        isolated_focus("123")
    with patch("jarvis.tools.gui_isolated.subprocess.run") as run:
        assert isolated_click(10, 20) == "Clicked isolated desktop at (10, 20)"
        assert isolated_type("hello") == "Typed on isolated desktop: hello"
        assert isolated_keypress("enter") == "Pressed key on isolated desktop: enter"
    assert run.call_count == 4

def test_real_gui():
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-test"}):
        with patch("jarvis.tools.gui_real.subprocess.run") as run:
            assert real_focus("456") == "Focused on real window 456"
            assert real_click(30, 40) == "Clicked real desktop at (30, 40)"
            assert real_type("world") == "Typed on real desktop: world"
            assert real_keypress("esc") == "Pressed key on real desktop: esc"
    assert run.call_count == 4
