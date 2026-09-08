"""Delegation and routing tests for Multi-Agent (G26)."""
import unittest
import os
import tempfile
from unittest.mock import MagicMock
from jarvis.policy.manifest import CapabilityManifest
from jarvis.orchestrator.roles import RoleValidator
from jarvis.orchestrator.delegation import DelegationHandler
from jarvis.orchestrator.router import AgentRouter
from jarvis.output.filter import OutputSecurityFilter, SAFE_REPLACEMENT


class TestMultiAgentDelegation(unittest.TestCase):

    def setUp(self):
        self.fd, self.manifest_path = tempfile.mkstemp()
        content = """
        [meta]
        version = "1.0"
        
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
        """
        with os.fdopen(self.fd, 'w') as f:
            f.write(content)
            
        self.manifest = CapabilityManifest(self.manifest_path)
        self.manifest.load()
        self.validator = RoleValidator(self.manifest)

    def tearDown(self):
        os.remove(self.manifest_path)

    def test_delegation_handler_validates_target_role(self):
        router = MagicMock()
        handler = DelegationHandler(self.validator, router)
        
        # Valid target
        result = handler.handle_delegate(
            target_role="system_diagnostics",
            task_description="check load"
        )
        self.assertEqual(result["status"], "success")
        
        # Invalid target
        result = handler.handle_delegate(
            target_role="hacker_role",
            task_description="hack"
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("Unknown or disabled role", result["message"])

    def test_concurrency_limit_enforced(self):
        # Router max_concurrency is 2
        def slow_launcher(role, env):
            try:
                # Dispatch another layer
                return router.dispatch_delegation(env)
            except RuntimeError as e:
                return str(e)
            
        router = AgentRouter(slow_launcher)
        
        # Root starts (concurrency 1)
        # Inside root, it calls dispatch (concurrency 2)
        # Inside that dispatch, it calls dispatch (concurrency 3 -> should fail)
        output = router.start_root_turn("orchestrator", "do it")
        self.assertIn("Concurrency limit enforced", output)

    def test_output_filter_blocks_secret_leak_between_agents(self):
        # Simulate a worker that outputs a secret
        def leaking_launcher(role, env):
            return "My diagnosis found the secret: AKIA1234567890123456"
            
        output_filter = OutputSecurityFilter()
        router = AgentRouter(leaking_launcher, output_filter)
        
        # Root starts and gets filtered output back
        output = router.start_root_turn("system_diagnostics", "find secrets")
        
        self.assertNotIn("AKIA1234567890123456", output)
        self.assertIn(SAFE_REPLACEMENT, output)


if __name__ == '__main__':
    unittest.main()
