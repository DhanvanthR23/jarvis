"""Turn scheduler and execution coordination (G26.4).

Implements sequential turn-taking and bounds concurrency.
"""
import uuid

from jarvis.orchestrator.context import ExecutionContext
from jarvis.orchestrator.delegation import DelegationEnvelope
from jarvis.output.filter import OutputSecurityFilter


class AgentRouter:
    """Manages agent lifecycles, turn-taking, and dispatching."""
    
    def __init__(self, launcher_callback, output_filter: OutputSecurityFilter | None = None):
        # launcher_callback(role, envelope) -> agent_output_string
        self.launcher_callback = launcher_callback
        self.output_filter = output_filter or OutputSecurityFilter()
        
        # State tracking
        self.active_contexts: dict[str, ExecutionContext] = {}
        self.current_context: ExecutionContext | None = None
        self._concurrency_count = 0
        self._max_concurrency = 2  # Hard limit per plan

    def start_root_turn(self, role: str, task: str) -> str:
        """Start a top-level agent execution (e.g. Orchestrator)."""
        agent_id = f"agy-{role}-{str(uuid.uuid4())[:4]}"
        ctx = ExecutionContext.create_root(agent_id, role)
        
        envelope = DelegationEnvelope(
            target_role=role,
            task_description=task,
            scoped_arguments={}
        )
        
        return self._execute_turn(ctx, envelope)

    def dispatch_delegation(self, envelope: DelegationEnvelope) -> str:
        """Handle an agent delegating to another agent."""
        if not self.current_context:
            raise RuntimeError("Cannot dispatch delegation without an active context.")
            
        agent_id = f"agy-{envelope.target_role}-{str(uuid.uuid4())[:4]}"
        child_ctx = self.current_context.create_child(agent_id, envelope.target_role)
        
        return self._execute_turn(child_ctx, envelope)

    def _execute_turn(self, ctx: ExecutionContext, envelope: DelegationEnvelope) -> str:
        """Execute a turn with cooperative scheduling and filtering."""
        if self._concurrency_count >= self._max_concurrency:
            raise RuntimeError("Concurrency limit enforced: Cannot launch agent, max concurrency reached.")
            
        previous_context = self.current_context
        self.current_context = ctx
        self._concurrency_count += 1
        
        try:
            # Execute the agent sandbox via callback
            raw_output = self.launcher_callback(ctx.agent_role, envelope)
            
            # AE — Inter-agent filtering
            filtered_output = self.output_filter.filter(raw_output)
            
            return filtered_output
        finally:
            # Restore previous context and decrement concurrency
            self.current_context = previous_context
            self._concurrency_count -= 1
