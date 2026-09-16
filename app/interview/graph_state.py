from typing import Any, TypedDict
from uuid import UUID

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.assessment_operations import FinalizeAssessmentResult
from app.domain.conversation_recovery import ConversationRecovery
from app.domain.follow_up_reasoning import FollowUpReasoning
from app.domain.response_evaluation import ResponseEvaluation


class InterviewGraphState(TypedDict, total=False):
    """Strongly typed state model for the LangGraph adaptive interview workflow."""

    # Session & Scope Identifiers
    session_id: UUID
    organization_id: UUID
    interview_definition_id: UUID
    current_turn: int
    min_turns: int
    max_turns: int

    # Current Turn Inputs
    candidate_response: str
    current_question: Any
    current_competency: Any
    current_difficulty: int
    interview_competencies: list[Any]
    used_question_ids: list[UUID]
    job_context: str | None

    # Intermediate Evaluation & Decision
    response_evaluation: ResponseEvaluation | None
    adaptive_decision: AdaptiveDecision | None
    action: AdaptiveAction | str | None
    follow_up_reasoning: FollowUpReasoning | None

    # Conversation Recovery (Module 15)
    conversation_recovery: ConversationRecovery | None
    redirect_message: str | None
    retry_count: int

    # Follow-Up & Next Turn State
    next_question: Any | None
    next_competency: Any | None
    next_difficulty: int | None
    why_this_follow_up: str | None  # Preserves user-facing explanation
    interview_status: str  # "IN_PROGRESS", "REDIRECTED", "COMPLETED", "FAILED"

    # MCP Assessment Operations (Module 16)
    assessment_finalized: bool | None
    finalization_result: FinalizeAssessmentResult | None

    # Execution Flags & Errors
    remaining_eligible_questions: bool
    error: str | None
