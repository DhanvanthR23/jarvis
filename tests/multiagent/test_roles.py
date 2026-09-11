"""Role and capability validation tests for Multi-Agent (G26)."""
import os
import tempfile
import unittest

from jarvis.orchestrator.roles import RoleValidator
from jarvis.policy.manifest import CapabilityManifest


class TestMultiAgentRoles(unittest.TestCase):

    def setUp(self):
        self.fd, self.manifest_path = tempfile.mkstemp()
        content = """
        [meta]
        version = "1.0"
        
        [capabilities]
        system_info = "safe"
        service_restart = "approval"
        agent_delegate = "safe"
        
        [roles.orchestrator]
        description = "Orchestrator"
        allowed_capabilities = ["agent_delegate"]
        max_execution_time = 60
        can_mutate = false
        
        [roles.system_diagnostics]
        description = "Diagnostics"
        allowed_capabilities = ["system_info"]
        max_execution_time = 45
        can_mutate = false
        
        [roles.system_maintenance]
        description = "Maintenance"
        allowed_capabilities = ["service_restart"]
        max_execution_time = 30
        can_mutate = true
        approval_required = true
        """
        with os.fdopen(self.fd, 'w') as f:
            f.write(content)
            
        self.manifest = CapabilityManifest(self.manifest_path)
        self.manifest.load()
        self.validator = RoleValidator(self.manifest)

    def tearDown(self):
        os.remove(self.manifest_path)

    def test_agent_cannot_call_unassigned_role_capability(self):
        # system_diagnostics has system_info, but not service_restart
        self.assertTrue(self.validator.is_tool_allowed_for_role('system_diagnostics', 'system_info'))
        self.assertFalse(self.validator.is_tool_allowed_for_role('system_diagnostics', 'service_restart'))

    def test_orchestrator_cannot_call_system_mutations_directly(self):
        # orchestrator only has agent_delegate
        self.assertTrue(self.validator.is_tool_allowed_for_role('orchestrator', 'agent_delegate'))
        self.assertFalse(self.validator.is_tool_allowed_for_role('orchestrator', 'service_restart'))
        self.assertFalse(self.validator.is_tool_allowed_for_role('orchestrator', 'system_info'))
        
    def test_delegation_requires_valid_target_role(self):
        # RoleValidator should return None for unknown roles
        self.assertIsNotNone(self.validator.get_role('system_diagnostics'))
        self.assertIsNone(self.validator.get_role('hacker_role'))


if __name__ == '__main__':
    unittest.main()
