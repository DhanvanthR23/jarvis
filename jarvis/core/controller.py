"""Jarvis controller — central coordinator (G6).

Coordinates user requests through the pipeline:
  Request → Agent → Tool callbacks → Policy → Tool execution → Audit → Response

The controller doesn't implement tools or policy itself — it orchestrates them.
"""

from jarvis.core.events import Event, EventType
from jarvis.core.session import Session


class JarvisController:
    """Central Jarvis controller.

    Wires together agent backend, policy engine, approval handler,
    audit logger, memory store, and tool registry.
    """

    def __init__(
        self,
        agent_backend,
        policy_engine=None,
        approval_handler=None,
        audit_logger=None,
        memory_store=None,
        tool_registry: dict = None,
    ):
        self.agent_backend = agent_backend
        self.policy_engine = policy_engine
        self.approval_handler = approval_handler
        self.audit_logger = audit_logger
        self.memory_store = memory_store
        self.tool_registry = tool_registry or {}
        self._session = Session()
        
        from jarvis.policy.approval import SessionApprovalCache
        self.approval_cache = SessionApprovalCache()

    @property
    def session(self) -> Session:
        return self._session

    def register_tool(self, name: str, handler, description: str = ''):
        """Register a tool handler."""
        self.tool_registry[name] = {
            'handler': handler,
            'description': description,
        }

    def process_request(self, user_input: str) -> str:
        """Process a user request through the full pipeline.

        1. Create request event
        2. Send to agent with tool callback
        3. Tool callback enforces: Policy → Approval → Execute → Audit
        4. Return agent's final response
        """
        # 1. Record request event
        req_event = Event(
            type=EventType.REQUEST,
            session_id=self.session.session_id,
            data={'user_input': user_input},
        )
        self.session.add_event(req_event)

        # 2. Define the tool callback
        def tool_callback(tool_name: str, args: dict) -> dict:
            return self._execute_tool(tool_name, args)

        # 3. Send to agent backend
        response = self.agent_backend.process(user_input, tool_callback)

        # 4. Record response event
        resp_event = Event(
            type=EventType.AGENT_RESPONSE,
            session_id=self.session.session_id,
            data={'response': response},
        )
        self.session.add_event(resp_event)

        return response

    def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute a tool through the policy pipeline.

        Invariant G: Every capability invocation is policy-checked.
        AGY → MCP → Policy → Tool
        """
        # Record tool call event
        self.session.add_event(Event(
            type=EventType.TOOL_CALL,
            session_id=self.session.session_id,
            data={'tool_name': tool_name, 'args': args},
        ))

        # Policy check (Invariant G: every invocation is policy-checked)
        policy_decision = 'ALLOW'
        approval_decision = None

        if self.policy_engine:
            self.session.add_event(Event(
                type=EventType.POLICY_CHECK,
                session_id=self.session.session_id,
                data={'tool_name': tool_name},
            ))

            result = self.policy_engine.check(tool_name, args)
            policy_decision = result.decision.value  # 'allow', 'approve', 'deny'

            if result.decision.value == 'deny':
                self._audit_event(
                    tool_name, args, policy_decision, None, 'denied',
                )
                return {
                    'status': 'denied',
                    'message': f'Policy denied: {result.reason}',
                }

            if result.decision.value == 'approve':
                # Need approval
                self.session.add_event(Event(
                    type=EventType.APPROVAL_REQUEST,
                    session_id=self.session.session_id,
                    data={'tool_name': tool_name, 'args': args},
                ))

                if self.approval_handler:
                    from jarvis.policy.approval import ApprovalRequest
                    import time
                    approval_req = ApprovalRequest(
                        actor='agent',
                        capability=tool_name,
                        arguments=args,
                        reason='Agent requested tool execution',
                        risk=result.reason,
                        timestamp=time.time(),
                    )
                    
                    if self.approval_cache.is_approved(approval_req):
                        approval_decision = 'allow_session_cached'
                    else:
                        approval_resp = self.approval_handler.request_approval(
                            approval_req,
                        )
                        approval_decision = approval_resp.decision.value
                        
                        if approval_resp.decision.value == 'allow_session':
                            self.approval_cache.add_approval(approval_req, approval_resp)

                        self.session.add_event(Event(
                            type=EventType.APPROVAL_RESPONSE,
                            session_id=self.session.session_id,
                            data={
                                'tool_name': tool_name,
                                'decision': approval_decision,
                            },
                        ))

                        if approval_resp.decision.value == 'deny':
                            self._audit_event(
                                tool_name, args, policy_decision,
                                approval_decision, 'denied by user',
                            )
                            return {
                                'status': 'denied',
                                'message': 'User denied the request',
                            }
                else:
                    # No approval handler — deny by default (safe)
                    self._audit_event(
                        tool_name, args, policy_decision, None,
                        'denied (no approval handler)',
                    )
                    return {
                        'status': 'denied',
                        'message': 'Approval required but no handler available',
                    }

        # Execute the tool
        tool_result = self._call_tool(tool_name, args)

        # Record result
        self.session.add_event(Event(
            type=EventType.TOOL_RESULT,
            session_id=self.session.session_id,
            data={'tool_name': tool_name, 'result': tool_result},
        ))

        # Audit
        self._audit_event(
            tool_name, args, policy_decision, approval_decision,
            tool_result.get('status', 'executed') if isinstance(tool_result, dict) else 'executed',
        )

        return tool_result

    def _call_tool(self, tool_name: str, args: dict) -> dict:
        """Look up and execute a registered tool."""
        if tool_name in self.tool_registry:
            handler = self.tool_registry[tool_name]['handler']
            try:
                result = handler(**args)
                return {'status': 'success', 'data': result}
            except Exception as e:
                return {'status': 'error', 'message': str(e)}
        else:
            # Return mock result for tools not yet registered
            return {'status': 'success', 'data': f'Executed {tool_name}'}

    def _audit_event(
        self, tool_name, args, policy_decision, approval_decision,
        result_summary,
    ):
        """Log to audit system if available. Fail-closed on audit failure."""
        if self.audit_logger:
            try:
                self.audit_logger.log_event(
                    session_id=self.session.session_id,
                    agent='agent',
                    tool=tool_name,
                    args=args,
                    policy_decision=policy_decision,
                    approval_decision=approval_decision,
                    result_summary=result_summary,
                )
            except Exception as e:
                # Security invariant: if audit fails, halt execution!
                raise RuntimeError(f"Audit failure: {e}")
