"""Tool registration helper."""

from jarvis.core.controller import JarvisController
from jarvis.tools import system, network, processes, logs, files

def register_readonly_tools(controller: JarvisController):
    """Register all G17 read-only tools on the controller."""
    controller.register_tool('system_info', system.system_info, 'Get basic system information')
    controller.register_tool('system_temperature', system.system_temperature, 'Get system temperature readings')
    
    controller.register_tool('network_interfaces', network.network_interfaces, 'Get network interfaces information')
    controller.register_tool('network_status', network.network_status, 'Get network routing and connection status')
    
    controller.register_tool('processes_list', processes.processes_list, 'List running processes')
    
    controller.register_tool('logs_search', logs.logs_search, 'Search system logs using journalctl')
    
    controller.register_tool('files_read', files.files_read, 'Read contents of a file')
    controller.register_tool('files_search', files.files_search, 'Search for files in a directory matching a pattern')
    
    # G19 Command Tools
    from jarvis.tools import commands
    controller.register_tool('command_execute', commands.command_execute, 'Execute an allowlisted command with structured arguments')
    
    # G18 Mutation Tools
    from jarvis.tools import mutations
    controller.register_tool('files_write', mutations.files_write, 'Write content to a file')
    controller.register_tool('service_restart', mutations.service_restart, 'Restart a systemd service')
    controller.register_tool('package_install', mutations.package_install, 'Install a system package using apt-get')

    # G21 Isolated GUI Tools
    from jarvis.tools import gui_isolated
    controller.register_tool('desktop_screenshot', gui_isolated.desktop_screenshot, 'Take a screenshot of the isolated desktop')
    controller.register_tool('desktop_windows', gui_isolated.desktop_windows, 'List windows in the isolated desktop')
    controller.register_tool('desktop_focus', gui_isolated.desktop_focus, 'Focus a window in the isolated desktop')
    controller.register_tool('desktop_click', gui_isolated.desktop_click, 'Click at coordinates on the isolated desktop')
    controller.register_tool('desktop_type', gui_isolated.desktop_type, 'Type text on the isolated desktop')
    controller.register_tool('desktop_keypress', gui_isolated.desktop_keypress, 'Press a key on the isolated desktop')

    # G22 Real Desktop Tools
    from jarvis.tools import gui_real
    controller.register_tool('desktop_observe', gui_real.desktop_observe, 'Observe the real desktop')
    controller.register_tool('real_desktop_focus', gui_real.desktop_focus, 'Focus a window on the real desktop')
    controller.register_tool('real_desktop_click', gui_real.desktop_click, 'Click at coordinates on the real desktop')
    controller.register_tool('real_desktop_type', gui_real.desktop_type, 'Type text on the real desktop')
    controller.register_tool('real_desktop_keypress', gui_real.desktop_keypress, 'Press a key on the real desktop')

    # G23 Browser Tools
    from jarvis.tools import browser
    controller.register_tool('browser_navigate', browser.browser_navigate, 'Navigate to a URL')
    controller.register_tool('browser_read', browser.browser_read, 'Read page content')
    controller.register_tool('browser_click', browser.browser_click, 'Click a browser element')
    controller.register_tool('browser_type', browser.browser_type, 'Type into a browser element')
    controller.register_tool('browser_download', browser.browser_download, 'Download a file from a URL')
    controller.register_tool('browser_upload', browser.browser_upload, 'Upload a file via browser')
