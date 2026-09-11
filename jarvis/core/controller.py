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
        tool_registry: dict | None = None,
        voice_session=None,
        output_filter=None,
    ):
        from jarvis.output.filter import OutputSecurityFilter
        
        self.agent_backend = agent_backend
        self.policy_engine = policy_engine
        self.approval_handler = approval_handler
        self.audit_logger = audit_logger
        self.memory_store = memory_store
        self.tool_registry = tool_registry or {}
        self.voice_session = voice_session
        self.output_filter = output_filter or OutputSecurityFilter()
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

    def process_request(self, user_input: str, is_voice: bool = False, transcript=None) -> str:
        """Process a user request through the pipeline."""
        
        # 1. Log utterance event
        if is_voice and transcript:
            self.session.add_event(Event(
                type='VOICE_UTTERANCE',
                session_id=self.session.session_id,
                data={'text': transcript.text, 'confidence': transcript.confidence},
            ))
        else:
            self.session.add_event(Event(
                type=EventType.REQUEST,
                session_id=self.session.session_id,
                data={'text': user_input},
            ))

        # 2. Check for Voice Confirmation
        if is_voice and transcript and self.voice_session:
            import time

            from jarvis.policy.approval import ApprovalDecision, ApprovalRequest, ApprovalResponse
            from jarvis.voice.confirmation import is_confirmation, process_confirmation
            
            self.voice_session.cleanup_expired()
            if is_confirmation(transcript):
                result = process_confirmation(transcript, self.voice_session)
                if result['status'] == 'rejected':
                    if result['reason'] == 'insufficient_confidence':
                        return self.output_filter.filter("I couldn't hear that clearly enough to confirm. Please repeat.")
                    return self.output_filter.filter("Confirmation rejected.")
                elif result['status'] == 'ambiguous':
                    return self.output_filter.filter("Multiple approvals pending. Please specify which one to confirm.")
                elif result['status'] == 'confirmed':
                    approval = result['approval']
                    # Create the synthetic ApprovalRequest & Response to inject into the cache
                    req = ApprovalRequest(
                        actor='agent',
                        capability=approval.capability,
                        arguments=approval.arguments,
                        reason='Voice confirmed',
                        risk='approval'
                    )
                    resp = ApprovalResponse(
                        request_id=req.request_id,
                        decision=ApprovalDecision.ALLOW_SESSION,
                        responded_at=time.time(),
                        responded_by="voice_system",
                        expires_at=approval.expires_at
                    )
                    self.approval_cache.add_approval(req, resp)
                    
                    response = self.agent_backend.process("Approval confirmed. Proceed with the tool execution.", lambda t, a: self._execute_tool(t, a))
                    return self.output_filter.filter(response)

        def tool_callback(tool_name: str, args: dict) -> dict:
            return self._execute_tool(tool_name, args)

        # 3. Apply voice constraints
        if is_voice:
            prompt = (
                "<VOICE_MODE_ON>\n"
                "CRITICAL SYSTEM OVERRIDE: You are an AI assistant communicating EXCLUSIVELY over an audio Voice Interface. "
                "YOUR ENTIRE RESPONSE WILL BE READ ALOUD BY A TEXT-TO-SPEECH ENGINE.\n\n"
                "VOICE CONSTRAINTS (MUST OBEY):\n"
                "1. NO MARKDOWN: Never use tables, bolding (**), italics, hashes (#), or bullet points.\n"
                "2. NO TECHNICAL JARGON: Never output raw JSON, code blocks, IP addresses, or terminal commands.\n"
                "3. CONVERSATIONAL SUMMARY: If a tool returns complex data (like network diagnostics), you MUST summarize it into 1 or 2 short, naturally spoken sentences. For example, 'Your Wi-Fi is connected and working perfectly' instead of listing the gateway IP.\n"
                "4. If you output a markdown table or a list, the text-to-speech engine will crash and you will fail your core directive.\n"
                "</VOICE_MODE_ON>\n\n"
                f"User said: {user_input}"
            )
        else:
            prompt = user_input

        response = self.agent_backend.process(prompt, tool_callback)

        # 4. Record response event
        resp_event = Event(
            type=EventType.AGENT_RESPONSE,
            session_id=self.session.session_id,
            data={'response': response},
        )
        self.session.add_event(resp_event)

        return self.output_filter.filter(response)

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
                    import time

                    from jarvis.policy.approval import ApprovalRequest
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
                            
                        if approval_resp.decision.value == 'pending':
                            self._audit_event(
                                tool_name, args, policy_decision,
                                approval_decision, 'pending voice confirmation',
                            )
                            return {
                                'status': 'pending_approval',
                                'message': 'Requires voice confirmation. Say: "Yes Jarvis, confirm".'
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
            # Fail closed for unregistered tools
            return {'status': 'error', 'message': f'Tool {tool_name} is not registered.'}

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
