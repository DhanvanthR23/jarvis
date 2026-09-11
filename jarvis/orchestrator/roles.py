"""Role-based permission validation for Multi-Agent (G26).

Ensures that agents can only execute tools defined in their role.
"""

from jarvis.policy.manifest import CapabilityManifest, Role


class RoleValidator:
    """Validates tool execution against an agent's assigned role."""
    
    def __init__(self, manifest: CapabilityManifest):
        self.manifest = manifest

    def is_tool_allowed_for_role(self, role_name: str, tool_name: str) -> bool:
        """Check if a tool is explicitly permitted for a given role."""
        if role_name not in self.manifest.roles:
            return False
            
        role = self.manifest.roles[role_name]
        return tool_name in role.allowed_capabilities

    def get_role(self, role_name: str) -> Role | None:
        """Get the role definition from the manifest."""
        return self.manifest.roles.get(role_name)
