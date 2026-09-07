from jarvis.tools.gui_isolated import (
    desktop_screenshot,
    desktop_windows,
    desktop_focus as isolated_focus,
    desktop_click as isolated_click,
    desktop_type as isolated_type,
    desktop_keypress as isolated_keypress,
)
from jarvis.tools.gui_real import (
    desktop_observe,
    desktop_focus as real_focus,
    desktop_click as real_click,
    desktop_type as real_type,
    desktop_keypress as real_keypress,
)

def test_isolated_gui():
    assert desktop_screenshot() == "Took a screenshot of the isolated desktop"
    assert desktop_windows() == ["Mock Window 1", "Mock Window 2"]
    assert isolated_focus("123") == "Focused on window 123"
    assert isolated_click(10, 20) == "Clicked at (10, 20)"
    assert isolated_type("hello") == "Typed: hello"
    assert isolated_keypress("enter") == "Pressed key: enter"

def test_real_gui():
    assert desktop_observe() == "Observed the real desktop"
    assert real_focus("456") == "Focused on real window 456"
    assert real_click(30, 40) == "Clicked real desktop at (30, 40)"
    assert real_type("world") == "Typed on real desktop: world"
    assert real_keypress("esc") == "Pressed key on real desktop: esc"
