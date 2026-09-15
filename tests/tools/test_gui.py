import os
from unittest.mock import patch, MagicMock

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
    desktop_type as real_type,
)


def test_isolated_desktop_windows_niri_fallback():
    """desktop_windows falls back to niri msg when wlrctl is absent."""
    niri_json = '[{"id": 3, "title": "Terminal", "app_id": "foot", "workspace_id": 1, "is_focused": true}]'

    def mock_run(cmd, **kwargs):
        if cmd[0] == "wlrctl":
            raise FileNotFoundError("wlrctl not found")
        result = MagicMock()
        result.returncode = 0
        result.stdout = niri_json
        return result

    with patch("jarvis.tools.gui_isolated.subprocess.run", side_effect=mock_run):
        windows = desktop_windows()
    assert len(windows) == 1
    assert 'ID 3' in windows[0]
    assert 'Terminal' in windows[0]
    assert '(focused)' in windows[0]


def test_isolated_desktop_windows_no_compositor():
    """desktop_windows returns an error when no compositor tools are found."""
    def mock_run(cmd, **kwargs):
        raise FileNotFoundError("not found")

    with patch("jarvis.tools.gui_isolated.subprocess.run", side_effect=mock_run):
        windows = desktop_windows()
    assert len(windows) == 1
    assert "Error" in windows[0]


def test_isolated_desktop_focus_niri_fallback():
    """desktop_focus falls back to niri msg when wlrctl is absent."""
    def mock_run(cmd, **kwargs):
        if cmd[0] == "wlrctl":
            raise FileNotFoundError("wlrctl not found")
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    with patch("jarvis.tools.gui_isolated.subprocess.run", side_effect=mock_run):
        result = isolated_focus("3")
    assert "Focused window ID 3" in result


def test_isolated_gui_click_type_keypress():
    """The isolated GUI click/type/keypress use subprocess."""
    with patch("jarvis.tools.gui_isolated.subprocess.run") as run:
        assert isolated_click(10, 20) == "Clicked isolated desktop at (10, 20)"
        assert isolated_type("hello") == "Typed on isolated desktop: hello"
        assert isolated_keypress("enter") == "Pressed key on isolated desktop: enter"
    assert run.call_count == 4


def test_real_gui_focus_niri():
    """real_desktop_focus uses niri msg on the real desktop."""
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-test"}):
        with patch("jarvis.tools.gui_real.subprocess.run", side_effect=mock_run):
            result = real_focus("456")
    assert "Focused real window ID 456" in result


def test_real_gui_click_type_keypress():
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-test"}):
        with patch("jarvis.tools.gui_real.subprocess.run") as run:
            assert real_click(30, 40) == "Clicked real desktop at (30, 40)"
            assert real_type("world") == "Typed on real desktop: world"
            assert real_keypress("esc") == "Pressed key on real desktop: esc"
    assert run.call_count == 4
