from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.conversation_recovery import ConversationRecovery
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.conversation_recovery import ConversationRecoveryService
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import AdaptiveInterviewOrchestrator


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_eval(
    demonstrated_level: int = 1,
    is_off_topic: bool = True,
    off_topic_reason: str | None = "Candidate discussed culinary recipes instead of the technical question",
    competency_id: Any = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        competency_id=competency_id or uuid4(),
        evidence_summary="Candidate response was off-topic.",
        demonstrated_level=demonstrated_level,
        depth_score=1.0,
        relevance_score=0.5,
        technical_accuracy_score=1.0,
        confidence=0.9,
        strengths=[],
        gaps=["Did not answer the technical question"],
        is_off_topic=is_off_topic,
        off_topic_reason=off_topic_reason,
    )


def make_decision(
    action: AdaptiveAction = AdaptiveAction.REDIRECT,
    target_difficulty: int | None = 2,
    target_competency_id: Any = None,
    reason: str = "Candidate response was off-topic.",
    based_on_turn: int = 1,
    confidence: float = 0.9,
) -> AdaptiveDecision:
    if action == AdaptiveAction.COMPLETE:
        target_difficulty = None
    return AdaptiveDecision(
        action=action,
        target_difficulty=target_difficulty,
        target_competency_id=target_competency_id or uuid4(),
        reason=reason,
        based_on_turn=based_on_turn,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Unit Tests: ConversationRecovery Domain Contract
# ---------------------------------------------------------------------------

def test_valid_recovery_contract():
    recovery = ConversationRecovery(
        action=AdaptiveAction.REDIRECT,
        redirect_message="Let's stay with the current question: Describe how you would investigate a production API outage.",
        original_question_text="Describe how you would investigate a production API outage.",
        off_topic_reason="Candidate described cooking biryani",
        retry_count=0,
        max_retries=2,
        should_re_evaluate=True,
        is_max_retries_exceeded=False,
    )
    assert recovery.action == AdaptiveAction.REDIRECT
    assert "production API outage" in recovery.redirect_message
    assert recovery.retry_count == 0
    assert recovery.max_retries == 2
    assert recovery.should_re_evaluate is True
    assert recovery.is_max_retries_exceeded is False


def test_blank_redirect_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ConversationRecovery(
            action=AdaptiveAction.REDIRECT,
            redirect_message="   ",
            original_question_text="Valid question",
        )
    assert "redirect_message cannot be blank" in str(exc_info.value)


def test_blank_original_question_text_rejected():
    with pytest.raises(ValidationError) as exc_info:
        ConversationRecovery(
            action=AdaptiveAction.REDIRECT,
            redirect_message="Valid redirect message",
            original_question_text="   ",
        )
    assert "original_question_text cannot be blank" in str(exc_info.value)


def test_retry_count_and_max_retries_bounds():
    with pytest.raises(ValidationError):
        ConversationRecovery(
            redirect_message="Valid redirect",
            original_question_text="Valid question",
            retry_count=-1,
        )

    with pytest.raises(ValidationError):
        ConversationRecovery(
            redirect_message="Valid redirect",
            original_question_text="Valid question",
            max_retries=0,
        )


# ---------------------------------------------------------------------------
# Unit Tests: ConversationRecoveryService Behavior
# ---------------------------------------------------------------------------

def test_off_topic_response_creates_redirect():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Describe how you would investigate a production API outage.")
    eval_res = make_eval(is_off_topic=True)
    decision = make_decision(action=AdaptiveAction.REDIRECT)

    recovery = service.recover(
        question=question,
        evaluation=eval_res,
        decision=decision,
        retry_count=0,
    )

    assert recovery.action == AdaptiveAction.REDIRECT
    assert "production API outage" in recovery.redirect_message
    assert recovery.is_max_retries_exceeded is False
    assert recovery.should_re_evaluate is True


def test_original_question_preserved():
    service = ConversationRecoveryService()
    question = SimpleNamespace(
        id=uuid4(),
        question_text="Explain database sharding strategies.",
    )
    eval_res = make_eval()
    decision = make_decision()

    recovery = service.recover(
        question=question,
        evaluation=eval_res,
        decision=decision,
        retry_count=0,
    )

    assert recovery.original_question == question
    assert recovery.original_question_text == "Explain database sharding strategies."
    assert "Explain database sharding strategies." in recovery.redirect_message


def test_redirect_is_polite_and_neutral():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="How do you handle microservices latency?")
    eval_res = make_eval(off_topic_reason="Candidate talked about vacations")
    decision = make_decision()

    recovery = service.recover(
        question=question,
        evaluation=eval_res,
        decision=decision,
        retry_count=0,
    )

    forbidden_phrases = [
        "that answer is wrong",
        "you failed",
        "your response was irrelevant",
        "bad answer",
        "lazy",
        "incompetent",
        "unprepared",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in recovery.redirect_message.lower()


def test_redirect_does_not_expose_scores():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain eventual consistency.")
    eval_res = make_eval()
    decision = make_decision()

    recovery = service.recover(
        question=question,
        evaluation=eval_res,
        decision=decision,
        retry_count=0,
    )

    forbidden_terms = [
        "depth_score",
        "relevance_score",
        "technical_accuracy",
        "confidence score",
        "0.5/5.0",
        "1.0/5.0",
    ]
    for term in forbidden_terms:
        assert term not in recovery.redirect_message.lower()


def test_redirect_does_not_expose_demonstrated_level():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain eventual consistency.")
    eval_res = make_eval(demonstrated_level=1)
    decision = make_decision()

    recovery = service.recover(
        question=question,
        evaluation=eval_res,
        decision=decision,
        retry_count=0,
    )

    forbidden_terms = [
        "demonstrated level",
        "demonstrated_level",
        "level 1",
    ]
    for term in forbidden_terms:
        assert term not in recovery.redirect_message.lower()


def test_retry_count_starts_correctly():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain rate limiting algorithms.")
    recovery = service.recover(
        question=question,
        evaluation=make_eval(),
        decision=make_decision(),
        retry_count=0,
    )
    assert recovery.retry_count == 0
    assert recovery.is_max_retries_exceeded is False


def test_retry_count_increments():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain rate limiting algorithms.")
    recovery1 = service.recover(
        question=question,
        evaluation=make_eval(),
        decision=make_decision(),
        retry_count=1,
    )
    assert recovery1.retry_count == 1
    assert recovery1.is_max_retries_exceeded is False


def test_second_redirect_remains_graceful():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain rate limiting algorithms.")
    recovery = service.recover(
        question=question,
        evaluation=make_eval(),
        decision=make_decision(),
        retry_count=1,
    )
    assert "Before moving on" in recovery.redirect_message
    assert "rate limiting algorithms" in recovery.redirect_message
    assert recovery.is_max_retries_exceeded is False
    assert recovery.should_re_evaluate is True


def test_retry_limit_prevents_infinite_loop():
    service = ConversationRecoveryService(default_max_retries=2)
    question = SimpleNamespace(question_text="Explain rate limiting algorithms.")
    recovery = service.recover(
        question=question,
        evaluation=make_eval(),
        decision=make_decision(),
        retry_count=2,
        max_retries=2,
    )
    assert recovery.is_max_retries_exceeded is True
    assert recovery.should_re_evaluate is False
    assert "reached the redirect limit" in recovery.redirect_message.lower()


def test_deterministic_output():
    service = ConversationRecoveryService()
    question = SimpleNamespace(question_text="Explain cache invalidation.")
    ev = make_eval()
    dec = make_decision()

    r1 = service.recover(question=question, evaluation=ev, decision=dec, retry_count=0)
    r2 = service.recover(question=question, evaluation=ev, decision=dec, retry_count=0)

    assert r1.model_dump() == r2.model_dump()


def test_no_llm_or_network_dependency():
    service = ConversationRecoveryService()
    assert not hasattr(service, "provider")
    assert not hasattr(service, "client")
    assert not hasattr(service, "api_key")


# ---------------------------------------------------------------------------
# Integration with AdaptiveInterviewOrchestrator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_redirect_node_stores_recovery_state():
    comp_id = uuid4()
    comp = SimpleNamespace(id=comp_id, name="Incident Management")
    q = SimpleNamespace(
        id=uuid4(),
        difficulty_level=2,
        competency_id=comp_id,
        question_text="Describe how you would investigate a production API outage.",
    )

    off_topic_eval = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate discussed cooking biryani.",
        demonstrated_level=1,
        depth_score=1.0,
        relevance_score=0.5,
        technical_accuracy_score=1.0,
        confidence=0.9,
        strengths=[],
        gaps=["Did not address API outage"],
        is_off_topic=True,
        off_topic_reason="Candidate described cooking biryani for family",
    )
    mock_service = MagicMock()
    mock_service.evaluate_answer = AsyncMock(return_value=off_topic_eval)

    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=mock_service,
    )

    state: InterviewGraphState = {
        "candidate_response": "I cooked biryani for my family and everyone loved it.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 1,
        "min_turns": 5,
        "max_turns": 10,
        "retry_count": 0,
        "interview_status": "IN_PROGRESS",
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "REDIRECTED"
    assert result["next_question"] == q
    assert result["retry_count"] == 1
    assert "conversation_recovery" in result
    assert isinstance(result["conversation_recovery"], ConversationRecovery)
    assert result["redirect_message"] is not None
    assert "production API outage" in result["redirect_message"]


@pytest.mark.asyncio
async def test_orchestrator_max_retries_transition():
    comp_id = uuid4()
    comp = SimpleNamespace(id=comp_id, name="Incident Management")
    q = SimpleNamespace(
        id=uuid4(),
        difficulty_level=2,
        competency_id=comp_id,
        question_text="Describe how you would investigate a production API outage.",
    )

    off_topic_eval = make_eval(is_off_topic=True, competency_id=comp_id)
    mock_service = MagicMock()
    mock_service.evaluate_answer = AsyncMock(return_value=off_topic_eval)

    next_q = SimpleNamespace(id=uuid4(), difficulty_level=2, competency_id=comp_id, question_text="Next topic question")

    async def mock_selector(**kwargs):
        return next_q

    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=mock_service,
        question_selector=mock_selector,
    )

    # State where retry_count is already at limit (2)
    state: InterviewGraphState = {
        "candidate_response": "Still talking about biryani recipes.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 2,
        "min_turns": 5,
        "max_turns": 10,
        "retry_count": 2,
        "interview_status": "IN_PROGRESS",
    }

    result = await orchestrator.run_turn(state)

    # Must transition without infinite redirect loop
    assert result["interview_status"] in ("IN_PROGRESS", "COMPLETED")
    assert result["conversation_recovery"].is_max_retries_exceeded is True
    assert result["retry_count"] == 0  # Reset for next question


# ---------------------------------------------------------------------------
# Required Manual Deliverable Scenario
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_scenario_biryani_off_topic_recovery_and_reentry():
    """Manual Scenario:
    Turn 1: Question about production API outage -> Candidate discusses cooking biryani ->
            Module 11 detects off-topic -> Module 12 REDIRECT -> Module 14 explains why ->
            Module 15 generates polite redirect preserving original question.
    Turn 2: Candidate answers with monitoring & logs investigation ->
            Normal evaluation pipeline resumes -> Valid demonstrated level scored.
    """
    comp_id = uuid4()
    comp = SimpleNamespace(id=comp_id, name="Production Reliability")
    question = SimpleNamespace(
        id=uuid4(),
        difficulty_level=2,
        competency_id=comp_id,
        question_text="Describe how you would investigate a production API outage.",
    )

    # Turn 1: Candidate is off-topic
    eval_turn_1 = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate discussed biryani cooking recipe.",
        demonstrated_level=1,
        depth_score=1.0,
        relevance_score=0.5,
        technical_accuracy_score=1.0,
        confidence=0.9,
        strengths=[],
        gaps=["Did not address production outage"],
        is_off_topic=True,
        off_topic_reason="Candidate discussed culinary recipes instead of technical outage investigation",
    )

    # Turn 2: Candidate provides a strong technical answer
    eval_turn_2 = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate clearly outlined monitoring checks, service isolation, reproduction, and mitigation.",
        demonstrated_level=3,
        depth_score=3.5,
        relevance_score=4.5,
        technical_accuracy_score=4.0,
        confidence=0.92,
        strengths=["Systematic diagnosis using observability logs", "Mitigation before root-cause analysis"],
        gaps=[],
        is_off_topic=False,
    )

    mock_response_service = MagicMock()
    mock_response_service.evaluate_answer = AsyncMock(side_effect=[eval_turn_1, eval_turn_2])

    next_question_after_success = SimpleNamespace(
        id=uuid4(),
        difficulty_level=3,
        competency_id=comp_id,
        question_text="How would you design automated alerting to prevent similar outages?",
    )

    async def mock_selector(**kwargs):
        return next_question_after_success

    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=mock_response_service,
        question_selector=mock_selector,
    )

    # --- Execute Turn 1 (Off-topic) ---
    state_turn_1: InterviewGraphState = {
        "candidate_response": "I recently cooked biryani for my family and everyone liked it.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 1,
        "min_turns": 5,
        "max_turns": 10,
        "retry_count": 0,
        "interview_status": "IN_PROGRESS",
    }

    result_turn_1 = await orchestrator.run_turn(state_turn_1)

    # Verify Turn 1 Recovery Output
    assert result_turn_1["action"] == AdaptiveAction.REDIRECT
    assert result_turn_1["interview_status"] == "REDIRECTED"
    assert result_turn_1["next_question"] == question  # Preserves original question!
    assert result_turn_1["retry_count"] == 1
    assert "conversation_recovery" in result_turn_1
    recovery_1: ConversationRecovery = result_turn_1["conversation_recovery"]
    assert "production API outage" in recovery_1.redirect_message
    assert recovery_1.is_max_retries_exceeded is False

    # --- Execute Turn 2 (Candidate answers with proper technical steps) ---
    state_turn_2: InterviewGraphState = {
        "candidate_response": "I would first check monitoring and logs, identify the failing service, reproduce the issue if possible, and then mitigate the impact before investigating root cause.",
        "current_question": result_turn_1["next_question"],
        "current_competency": result_turn_1["next_competency"],
        "current_difficulty": result_turn_1["next_difficulty"],
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 2,
        "min_turns": 5,
        "max_turns": 10,
        "retry_count": result_turn_1["retry_count"],
        "interview_status": "IN_PROGRESS",
    }

    result_turn_2 = await orchestrator.run_turn(state_turn_2)

    # Verify Turn 2 returned to normal evaluation and progression!
    assert result_turn_2["interview_status"] == "IN_PROGRESS"
    assert result_turn_2["action"] in (AdaptiveAction.ESCALATE, AdaptiveAction.PROBE, AdaptiveAction.ADVANCE)
    assert result_turn_2["response_evaluation"].demonstrated_level == 3
    assert result_turn_2["response_evaluation"].is_off_topic is False
    assert result_turn_2["next_question"] == next_question_after_success
