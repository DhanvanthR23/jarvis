import os
import pytest
from unittest.mock import patch, MagicMock

from jarvis.tools.gui_real import (
    desktop_observe, 
    WaylandProxyError, 
    RateLimitError,
    _verify_wayland_proxy
)

@pytest.fixture(autouse=True)
def reset_time():
    import jarvis.tools.gui_real as gr
    gr._LAST_SCREENSHOT_TIME = 0.0

def test_verify_wayland_proxy_raw():
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}):
        with pytest.raises(WaylandProxyError, match="Raw WAYLAND_DISPLAY .* is not allowed"):
            _verify_wayland_proxy()

def test_verify_wayland_proxy_missing():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(WaylandProxyError, match="WAYLAND_DISPLAY is not set"):
            _verify_wayland_proxy()

def test_verify_wayland_proxy_valid():
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        # Should not raise
        _verify_wayland_proxy()

@patch("subprocess.run")
def test_desktop_observe_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"fakeimage"
            res = desktop_observe()
            assert isinstance(res, list)
            assert res[0]["text"] == "Real desktop screenshot taken."

@patch("subprocess.run")
@pytest.mark.skipif(
    not __import__('importlib').util.find_spec('PIL'),
    reason="Pillow (PIL) not installed"
)
def test_desktop_observe_with_pil(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        with patch("jarvis.tools.gui_real.HAS_PIL", True):
            with patch("PIL.Image.open") as mock_pil_open:
                mock_img = MagicMock()
                mock_img.mode = "RGBA"
                mock_converted_img = MagicMock()
                mock_img.convert.return_value = mock_converted_img
                mock_pil_open.return_value.__enter__.return_value = mock_img
                
                with patch("builtins.open", MagicMock()) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = b"fakeimage"
                    res = desktop_observe()
                    assert isinstance(res, list)
                    assert res[0]["text"] == "Real desktop screenshot taken."
                    mock_img.thumbnail.assert_called_once()
                    mock_img.convert.assert_called_once_with("RGB")
                    mock_converted_img.save.assert_called_once()

@patch("subprocess.run")
def test_desktop_observe_rate_limit(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"fakeimage"
            desktop_observe()
            with pytest.raises(RateLimitError, match="Screenshot frequency exceeded"):
                desktop_observe()

from jarvis.tools.gui_real import desktop_click, desktop_type, desktop_keypress

@patch("subprocess.run")
def test_desktop_click(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        res = desktop_click(10, 20)
        assert "Clicked real desktop at (10, 20)" in res
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["wlrctl", "pointer", "move", "10", "20"], check=True, capture_output=True)
        mock_run.assert_any_call(["wlrctl", "pointer", "click", "left"], check=True, capture_output=True)

@patch("subprocess.run")
def test_desktop_type(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        res = desktop_type("hello")
        assert "Typed on real desktop: hello" in res
        mock_run.assert_called_once_with(["wtype", "hello"], check=True, capture_output=True)

@patch("subprocess.run")
def test_desktop_keypress(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-proxy-1"}):
        res = desktop_keypress("Return")
        assert "Pressed key on real desktop: Return" in res
        mock_run.assert_called_once_with(["wtype", "-k", "Return"], check=True, capture_output=True)


def test_capabilities_mapped():
    from jarvis.tools.gui_real import desktop_focus
    assert hasattr(desktop_observe, "required_capabilities")
    assert "CAP_WAYLAND_OBSERVE" in desktop_observe.required_capabilities

    assert hasattr(desktop_click, "required_capabilities")
    assert "CAP_WAYLAND_CONTROL" in desktop_click.required_capabilities

    assert hasattr(desktop_type, "required_capabilities")
    assert "CAP_WAYLAND_CONTROL" in desktop_type.required_capabilities

    assert hasattr(desktop_keypress, "required_capabilities")
    assert "CAP_WAYLAND_CONTROL" in desktop_keypress.required_capabilities

    assert hasattr(desktop_focus, "required_capabilities")
    assert "CAP_WAYLAND_CONTROL" in desktop_focus.required_capabilities
