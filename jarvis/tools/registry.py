"""Tool registration helper."""

from jarvis.core.controller import JarvisController
from jarvis.tools import system, network, processes, logs, files

def register_readonly_tools(controller: JarvisController):
    """Register all G17 read-only tools on the controller."""
    controller.register_tool('system.info', system.system_info, 'Get basic system information')
    controller.register_tool('system.temperature', system.system_temperature, 'Get system temperature readings')
    
    controller.register_tool('network.interfaces', network.network_interfaces, 'Get network interfaces information')
    controller.register_tool('network.status', network.network_status, 'Get network routing and connection status')
    
    controller.register_tool('processes.list', processes.processes_list, 'List running processes')
    
    controller.register_tool('logs.search', logs.logs_search, 'Search system logs using journalctl')
    
    controller.register_tool('files.read', files.files_read, 'Read contents of a file')
    controller.register_tool('files.search', files.files_search, 'Search for files in a directory matching a pattern')
    
    # G19 Command Tools
    from jarvis.tools import commands
    controller.register_tool('command.execute', commands.command_execute, 'Execute an allowlisted command with structured arguments')
    
    # G18 Mutation Tools
    from jarvis.tools import mutations
    controller.register_tool('files.write', mutations.files_write, 'Write content to a file')
    controller.register_tool('service.restart', mutations.service_restart, 'Restart a systemd service')
    controller.register_tool('package.install', mutations.package_install, 'Install a system package using apt-get')
