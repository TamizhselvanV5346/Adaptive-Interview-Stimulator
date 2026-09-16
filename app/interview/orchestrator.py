from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.conversation_recovery import ConversationRecovery
from app.domain.follow_up_reasoning import FollowUpReasoning
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.adaptive_decision import AdaptiveDecisionEngine
from app.interview.conversation_recovery import ConversationRecoveryService
from app.interview.follow_up_reasoning import FollowUpReasoningService
from app.interview.graph_state import InterviewGraphState
from app.interview.question_selector import QuestionSelector
from app.mcp.assessment_operations import AssessmentOperationsMCP


class AdaptiveInterviewOrchestrator:
    """LangGraph-powered stateful orchestrator for adaptive interview execution."""

    def __init__(
        self,
        response_service: ResponseIntelligenceService | None = None,
        decision_engine: AdaptiveDecisionEngine | None = None,
        reasoning_service: FollowUpReasoningService | None = None,
        recovery_service: ConversationRecoveryService | None = None,
        mcp_service: AssessmentOperationsMCP | None = None,
        question_selector: Callable[..., Awaitable[Any | None]] | None = None,
        db: AsyncSession | None = None,
    ):
        self.response_service = response_service or ResponseIntelligenceService(provider=MockProvider())
        self.decision_engine = decision_engine or AdaptiveDecisionEngine()
        self.reasoning_service = reasoning_service or FollowUpReasoningService()
        self.recovery_service = recovery_service or ConversationRecoveryService()
        self.mcp_service = mcp_service or AssessmentOperationsMCP()
        self.db = db
        self._custom_question_selector = question_selector
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(InterviewGraphState)

        # Register core nodes
        workflow.add_node("evaluate_response", self._evaluate_response_node)
        workflow.add_node("make_adaptive_decision", self._make_adaptive_decision_node)
        workflow.add_node("generate_follow_up_reasoning", self._generate_follow_up_reasoning_node)

        # Register action nodes
        workflow.add_node("probe_question", self._probe_question_node)
        workflow.add_node("escalate_question", self._escalate_question_node)
        workflow.add_node("advance_question", self._advance_question_node)
        workflow.add_node("redirect_candidate", self._redirect_candidate_node)
        workflow.add_node("complete_interview", self._complete_interview_node)

        # Connect entry flow
        workflow.add_edge(START, "evaluate_response")
        workflow.add_edge("evaluate_response", "make_adaptive_decision")
        workflow.add_edge("make_adaptive_decision", "generate_follow_up_reasoning")

        # Connect conditional routing
        workflow.add_conditional_edges(
            "generate_follow_up_reasoning",
            self._route_decision,
            {
                "probe_question": "probe_question",
                "escalate_question": "escalate_question",
                "advance_question": "advance_question",
                "redirect_candidate": "redirect_candidate",
                "complete_interview": "complete_interview",
            },
        )

        # Connect action branches to termination
        workflow.add_edge("probe_question", END)
        workflow.add_edge("escalate_question", END)
        workflow.add_edge("advance_question", END)
        workflow.add_edge("redirect_candidate", END)
        workflow.add_edge("complete_interview", END)

        return workflow.compile()

    # -----------------------------------------------------------------------
    # Node implementations
    # -----------------------------------------------------------------------

    async def _evaluate_response_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Node 1: Evaluate candidate response against current question and competency."""
        # Validation checks
        if state.get("interview_status") == "COMPLETED":
            return {
                "error": "Cannot evaluate response for an already completed interview.",
                "interview_status": "COMPLETED",
            }

        question = state.get("current_question")
        competency = state.get("current_competency")

        if not question or not competency:
            return {
                "error": "Missing current_question or current_competency in graph state.",
                "interview_status": "FAILED",
            }

        candidate_response = state.get("candidate_response", "")

        try:
            evaluation = await self.response_service.evaluate_answer(
                question=question,
                answer=candidate_response,
                competency=competency,
                job_context=state.get("job_context"),
            )
            return {"response_evaluation": evaluation}
        except Exception as exc:
            return {
                "error": f"Response evaluation failed: {exc}",
                "interview_status": "FAILED",
            }

    async def _make_adaptive_decision_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Node 2: Deterministically decide the next adaptive action using Module 12."""
        if state.get("error") or state.get("interview_status") in ("FAILED", "COMPLETED"):
            return {}

        evaluation = state.get("response_evaluation")
        if not evaluation:
            return {
                "error": "Cannot make adaptive decision without valid response_evaluation.",
                "interview_status": "FAILED",
            }

        competency = state.get("current_competency")
        question = state.get("current_question")
        interview_competencies = state.get("interview_competencies", [])
        current_turn = state.get("current_turn", 1)
        min_turns = state.get("min_turns", 8)
        max_turns = state.get("max_turns", 12)
        remaining_questions = state.get("remaining_eligible_questions", True)

        try:
            decision: AdaptiveDecision = self.decision_engine.decide(
                evaluation=evaluation,
                competency=competency,
                interview_competencies=interview_competencies,
                current_question=question,
                current_turn=current_turn,
                min_turns=min_turns,
                max_turns=max_turns,
                remaining_eligible_questions=remaining_questions,
            )

            return {
                "adaptive_decision": decision,
                "action": decision.action,
                "why_this_follow_up": decision.reason,  # Preserves Module 12 rationale
            }
        except Exception as exc:
            return {
                "error": f"Adaptive decision engine failed: {exc}",
                "interview_status": "FAILED",
            }

    async def _generate_follow_up_reasoning_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Node 2b: Generate structured, user-visible FollowUpReasoning explaining the decision."""
        if state.get("error") or state.get("interview_status") in ("FAILED", "COMPLETED"):
            return {}

        decision = state.get("adaptive_decision")
        evaluation = state.get("response_evaluation")
        if not decision or not evaluation:
            return {}

        try:
            reasoning = self.reasoning_service.reason(
                decision=decision,
                evaluation=evaluation,
                competency=state.get("current_competency"),
                current_difficulty=state.get("current_difficulty", 1),
            )
            return {
                "follow_up_reasoning": reasoning,
                "why_this_follow_up": reasoning.reason,
            }
        except Exception as exc:
            return {
                "error": f"Follow-up reasoning generation failed: {exc}",
                "interview_status": "FAILED",
            }

    def _route_decision(self, state: InterviewGraphState) -> str:
        """Route conditionally based on the deterministic AdaptiveAction."""
        if state.get("error") or state.get("interview_status") in ("FAILED", "COMPLETED"):
            return "complete_interview"

        action = state.get("action")
        if isinstance(action, AdaptiveAction):
            action_value = action.value
        elif isinstance(action, str):
            action_value = action.upper()
        else:
            decision = state.get("adaptive_decision")
            action_value = decision.action.value if decision else AdaptiveAction.COMPLETE.value

        if action_value == AdaptiveAction.PROBE.value:
            return "probe_question"
        if action_value == AdaptiveAction.ESCALATE.value:
            return "escalate_question"
        if action_value == AdaptiveAction.ADVANCE.value:
            return "advance_question"
        if action_value == AdaptiveAction.REDIRECT.value:
            return "redirect_candidate"
        if action_value == AdaptiveAction.COMPLETE.value:
            return "complete_interview"

        return "complete_interview"

    # -----------------------------------------------------------------------
    # Action Nodes
    # -----------------------------------------------------------------------

    async def _probe_question_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Handle PROBE action: Target same competency for deeper evidence."""
        decision = state.get("adaptive_decision")
        curr_comp = state.get("current_competency")
        curr_comp_id = decision.target_competency_id if decision else self._extract_id(curr_comp)
        target_diff = (
            decision.target_difficulty
            if decision and decision.target_difficulty is not None
            else state.get("current_difficulty", 1)
        )

        next_q = await self._query_next_question(
            state=state,
            competency_id=curr_comp_id,
            difficulty_level=target_diff,
        )

        if next_q:
            return {
                "next_question": next_q,
                "next_competency": curr_comp,
                "next_difficulty": target_diff,
                "interview_status": "IN_PROGRESS",
            }

        return {
            "next_question": None,
            "next_difficulty": None,
            "interview_status": "COMPLETED",
            "why_this_follow_up": "No further eligible probe questions remain. Concluding interview.",
        }

    async def _escalate_question_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Handle ESCALATE action: Increase difficulty on current competency."""
        decision = state.get("adaptive_decision")
        curr_comp = state.get("current_competency")
        curr_comp_id = decision.target_competency_id if decision else self._extract_id(curr_comp)
        target_diff = decision.target_difficulty if decision else 3

        next_q = await self._query_next_question(
            state=state,
            competency_id=curr_comp_id,
            difficulty_level=target_diff,
        )

        if next_q:
            return {
                "next_question": next_q,
                "next_competency": curr_comp,
                "next_difficulty": target_diff,
                "interview_status": "IN_PROGRESS",
            }

        return {
            "next_question": None,
            "next_difficulty": None,
            "interview_status": "COMPLETED",
            "why_this_follow_up": "No further eligible questions at escalated difficulty. Concluding interview.",
        }

    async def _advance_question_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Handle ADVANCE action: Transition to next configured competency."""
        decision = state.get("adaptive_decision")
        target_comp_id = decision.target_competency_id if decision else None
        target_diff = decision.target_difficulty if decision else 3

        next_comp = self._find_competency(target_comp_id, state.get("interview_competencies", []))

        next_q = await self._query_next_question(
            state=state,
            competency_id=target_comp_id,
            difficulty_level=target_diff,
        )

        if next_q:
            return {
                "next_question": next_q,
                "next_competency": next_comp or target_comp_id,
                "next_difficulty": target_diff,
                "interview_status": "IN_PROGRESS",
            }

        return {
            "next_question": None,
            "next_difficulty": None,
            "interview_status": "COMPLETED",
            "why_this_follow_up": "No further eligible questions for advanced competency. Concluding interview.",
        }

    async def _redirect_candidate_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Handle REDIRECT action: Conversational recovery for off-topic response."""
        decision = state.get("adaptive_decision")
        evaluation = state.get("response_evaluation")
        current_question = state.get("current_question")
        current_retries = state.get("retry_count", 0)

        recovery = self.recovery_service.recover(
            question=current_question,
            evaluation=evaluation,
            decision=decision,
            retry_count=current_retries,
        )

        reason = state.get("why_this_follow_up") or (decision.reason if decision else "Candidate response was off-topic.")

        if not recovery.is_max_retries_exceeded:
            return {
                "interview_status": "REDIRECTED",
                "next_question": current_question,
                "next_competency": state.get("current_competency"),
                "next_difficulty": state.get("current_difficulty"),
                "why_this_follow_up": reason,
                "conversation_recovery": recovery,
                "redirect_message": recovery.redirect_message,
                "retry_count": current_retries + 1,
            }

        # Max retries exceeded: Prevent infinite loops
        curr_comp = state.get("current_competency")
        curr_comp_id = self._extract_id(curr_comp)
        target_diff = state.get("current_difficulty", 2)

        interview_comps = state.get("interview_competencies", [])
        next_comp = None
        for ic in interview_comps:
            ic_id = getattr(ic, "competency_id", None) or (ic.get("competency_id") if isinstance(ic, dict) else None)
            if ic_id and ic_id != curr_comp_id:
                next_comp = getattr(ic, "competency", ic)
                curr_comp_id = ic_id
                break

        next_q = await self._query_next_question(
            state=state,
            competency_id=curr_comp_id,
            difficulty_level=target_diff,
        )

        if next_q:
            return {
                "interview_status": "IN_PROGRESS",
                "next_question": next_q,
                "next_competency": next_comp or state.get("current_competency"),
                "next_difficulty": target_diff,
                "why_this_follow_up": recovery.redirect_message,
                "conversation_recovery": recovery,
                "redirect_message": recovery.redirect_message,
                "retry_count": 0,
            }

        return {
            "interview_status": "COMPLETED",
            "next_question": None,
            "next_difficulty": None,
            "why_this_follow_up": recovery.redirect_message,
            "conversation_recovery": recovery,
            "redirect_message": recovery.redirect_message,
            "retry_count": 0,
        }

    async def _complete_interview_node(self, state: InterviewGraphState) -> dict[str, Any]:
        """Handle COMPLETE action: Conclude interview cleanly and execute MCP finalization."""
        if state.get("interview_status") == "FAILED":
            return {
                "next_question": None,
                "next_difficulty": None,
            }

        decision = state.get("adaptive_decision")
        reason = state.get("why_this_follow_up") or (decision.reason if decision else "Interview completed successfully.")

        result_payload: dict[str, Any] = {
            "interview_status": "COMPLETED",
            "next_question": None,
            "next_difficulty": None,
            "why_this_follow_up": reason,
            "assessment_finalized": False,
            "finalization_result": None,
        }

        # If session_id, organization_id, and db are available, execute MCP assessment finalization
        session_id = state.get("session_id")
        org_id = state.get("organization_id")
        if session_id and org_id and self.db:
            try:
                mcp_res = await self.mcp_service.finalize_assessment(
                    input_data={
                        "session_id": session_id,
                        "organization_id": org_id,
                        "final_turn": state.get("current_turn", 0),
                        "reason": reason,
                    },
                    db=self.db,
                )
                result_payload["assessment_finalized"] = mcp_res.success
                result_payload["finalization_result"] = mcp_res
            except Exception as exc:
                result_payload["assessment_finalized"] = False
                result_payload["error"] = f"MCP finalization error: {exc}"

        return result_payload

    # -----------------------------------------------------------------------
    # Execution & Query Helpers
    # -----------------------------------------------------------------------

    async def run_turn(self, state: InterviewGraphState) -> InterviewGraphState:
        """Execute a single adaptive interview turn through the compiled LangGraph workflow."""
        result = await self.graph.ainvoke(state)
        return dict(result)  # type: ignore[return-value]

    async def _query_next_question(
        self,
        state: InterviewGraphState,
        competency_id: UUID | None,
        difficulty_level: int | None,
    ) -> Any | None:
        """Query next eligible question using injected selector, database, or state question pool."""
        used_ids = state.get("used_question_ids", [])
        org_id = state.get("organization_id")
        def_id = state.get("interview_definition_id")

        if self._custom_question_selector:
            return await self._custom_question_selector(
                interview_definition_id=def_id,
                organization_id=org_id,
                competency_id=competency_id,
                difficulty_level=difficulty_level,
                used_question_ids=used_ids,
            )

        if self.db and def_id:
            return await QuestionSelector.select_next_question(
                db=self.db,
                interview_definition_id=def_id,
                organization_id=org_id,
                competency_id=competency_id,
                difficulty_level=difficulty_level,
                used_question_ids=used_ids,
            )

        return None

    def _extract_id(self, obj: Any) -> UUID | None:
        if obj is None:
            return None
        raw = getattr(obj, "id", None)
        if raw is None and isinstance(obj, dict):
            raw = obj.get("id")
        if isinstance(raw, str):
            try:
                return UUID(raw)
            except ValueError:
                return None
        return raw if isinstance(raw, UUID) else None

    def _find_competency(self, comp_id: UUID | None, interview_competencies: list[Any]) -> Any | None:
        if not comp_id:
            return None
        for ic in interview_competencies:
            ic_comp_id = getattr(ic, "competency_id", None)
            if ic_comp_id is None and isinstance(ic, dict):
                ic_comp_id = ic.get("competency_id")
            if ic_comp_id == comp_id:
                return getattr(ic, "competency", ic)
        return None


def create_interview_graph(
    response_service: ResponseIntelligenceService | None = None,
    decision_engine: AdaptiveDecisionEngine | None = None,
    reasoning_service: FollowUpReasoningService | None = None,
    recovery_service: ConversationRecoveryService | None = None,
    mcp_service: AssessmentOperationsMCP | None = None,
    question_selector: Callable[..., Awaitable[Any | None]] | None = None,
    db: AsyncSession | None = None,
) -> Any:
    """Convenience factory function creating an AdaptiveInterviewOrchestrator graph instance."""
    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=response_service,
        decision_engine=decision_engine,
        reasoning_service=reasoning_service,
        recovery_service=recovery_service,
        mcp_service=mcp_service,
        question_selector=question_selector,
        db=db,
    )
    return orchestrator.graph
