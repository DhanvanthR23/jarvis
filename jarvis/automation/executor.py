"""Automation executor — bridges scheduler to JarvisController (G25.5).

The executor is the ONLY path from scheduler to tool execution.
It creates an automation-specific execution context and routes through
the Controller's normal pipeline: Policy → AGY → MCP → Tool → Audit.
"""
from typing import Optional

from jarvis.automation.models import AutomationJob
from jarvis.automation.authorization import AutomationAuthorization
from jarvis.automation.scheduler import ExecutionRecord, ExecutionStatus
from jarvis.output.filter import OutputSecurityFilter


class AutomationExecutor:
    """Executes authorized automation jobs through the JarvisController.

    Never calls tools directly. Always routes through the controller's
    existing policy/approval/audit pipeline.
    """

    def __init__(self, controller, output_filter: Optional[OutputSecurityFilter] = None):
        self.controller = controller
        self.output_filter = output_filter or OutputSecurityFilter()

    def execute(self, job: AutomationJob, auth: AutomationAuthorization,
                record: ExecutionRecord) -> dict:
        """Execute a job through the controller pipeline.

        The controller sees this as an automation request with:
          actor = "automation"
          capability = job.capability
          arguments = job.arguments

        Policy still applies. OutputSecurityFilter still applies.
        """
        # Build the tool execution request
        result = self.controller._execute_tool(job.capability, job.arguments)

        # Filter output through OutputSecurityFilter
        if isinstance(result, dict) and 'data' in result:
            filtered = self.output_filter.filter(str(result['data']))
            result['filtered_output'] = filtered

        return result
