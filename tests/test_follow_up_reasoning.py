from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.follow_up_reasoning import FollowUpReasoning
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.follow_up_reasoning import FollowUpReasoningService
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import AdaptiveInterviewOrchestrator


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_eval(
    demonstrated_level: int = 2,
    strengths: list[str] | None = None,
    gaps: list[str] | None = None,
    is_off_topic: bool = False,
    off_topic_reason: str | None = None,
    depth_score: float = 2.5,
    relevance_score: float = 4.0,
    technical_accuracy_score: float = 3.5,
    confidence: float = 0.9,
    competency_id: Any = None,
    evidence_summary: str = "Candidate demonstrated basic understanding.",
) -> ResponseEvaluation:
    return ResponseEvaluation(
        competency_id=competency_id or uuid4(),
        evidence_summary=evidence_summary,
        demonstrated_level=demonstrated_level,
        depth_score=depth_score,
        relevance_score=relevance_score,
        technical_accuracy_score=technical_accuracy_score,
        confidence=confidence,
        strengths=strengths or ["Clear syntax understanding"],
        gaps=gaps or [],
        is_off_topic=is_off_topic,
        off_topic_reason=off_topic_reason,
    )


def make_decision(
    action: AdaptiveAction,
    target_difficulty: int | None = 2,
    target_competency_id: Any = None,
    reason: str = "Deterministic decision rule matched.",
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
# Unit Tests: FollowUpReasoning Model Validation
# ---------------------------------------------------------------------------

def test_valid_follow_up_reasoning_model():
    reasoning = FollowUpReasoning(
        action=AdaptiveAction.PROBE,
        reason="Your answer showed basic understanding.",
        evidence_basis=["Demonstrated level: 2", "Gap: error handling"],
        competency_name="Python Core",
        difficulty_change=0,
        user_visible=True,
    )
    assert reasoning.action == AdaptiveAction.PROBE
    assert reasoning.reason == "Your answer showed basic understanding."
    assert len(reasoning.evidence_basis) == 2
    assert reasoning.competency_name == "Python Core"
    assert reasoning.difficulty_change == 0
    assert reasoning.user_visible is True


def test_blank_reason_rejected():
    with pytest.raises(ValidationError) as exc_info:
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="   ",
            evidence_basis=["Valid evidence"],
        )
    assert "reason cannot be blank" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="",
            evidence_basis=["Valid evidence"],
        )
    assert "reason cannot be blank" in str(exc_info.value)


def test_blank_evidence_rejected():
    # Empty list
    with pytest.raises(ValidationError) as exc_info:
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="Valid reason text",
            evidence_basis=[],
        )
    assert "evidence_basis cannot be empty or blank" in str(exc_info.value)

    # Empty string inside list
    with pytest.raises(ValidationError) as exc_info:
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="Valid reason text",
            evidence_basis=["  "],
        )
    assert "evidence_basis items cannot be blank" in str(exc_info.value)


def test_difficulty_change_bounds():
    # Out of bounds (< -4 or > 4)
    with pytest.raises(ValidationError):
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            evidence_basis=["Evidence"],
            difficulty_change=5,
        )

    with pytest.raises(ValidationError):
        FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            evidence_basis=["Evidence"],
            difficulty_change=-5,
        )

    # Valid within bounds
    r = FollowUpReasoning(
        action=AdaptiveAction.ESCALATE,
        reason="Valid reason",
        evidence_basis=["Evidence"],
        difficulty_change=2,
    )
    assert r.difficulty_change == 2


# ---------------------------------------------------------------------------
# Unit Tests: FollowUpReasoningService Action Templates
# ---------------------------------------------------------------------------

def test_probe_reasoning_with_gap():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Distributed Systems")
    evaluation = make_eval(
        demonstrated_level=2,
        gaps=["handling network partitions under split-brain"],
    )
    decision = make_decision(action=AdaptiveAction.PROBE, target_difficulty=2)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=2,
    )

    assert result.action == AdaptiveAction.PROBE
    assert "Your answer showed basic understanding" in result.reason
    assert "handling network partitions under split-brain" in result.reason
    assert "The next question probes that gap." in result.reason
    assert result.difficulty_change == 0
    assert result.competency_name == "Distributed Systems"
    assert any("Demonstrated level: 2" in item for item in result.evidence_basis)
    assert any("handling network partitions" in item for item in result.evidence_basis)


def test_probe_reasoning_without_gap():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="System Architecture")
    evaluation = make_eval(demonstrated_level=2, gaps=[], depth_score=2.0, relevance_score=4.0)
    decision = make_decision(action=AdaptiveAction.PROBE, target_difficulty=2)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=2,
    )

    assert result.action == AdaptiveAction.PROBE
    assert "probe the same competency further" in result.reason
    assert result.difficulty_change == 0
    assert len(result.evidence_basis) >= 2


def test_escalate_reasoning_with_difficulty_progression():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Data Structures")
    evaluation = make_eval(
        demonstrated_level=3,
        strengths=["Optimal time complexity analysis using amortized bounds"],
    )
    decision = make_decision(action=AdaptiveAction.ESCALATE, target_difficulty=3)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=2,
    )

    assert result.action == AdaptiveAction.ESCALATE
    assert "increasing the challenge to difficulty 3" in result.reason
    assert "at difficulty 2" in result.reason
    assert result.difficulty_change == 1
    assert result.competency_name == "Data Structures"
    assert any("Previous difficulty: 2" in item for item in result.evidence_basis)
    assert any("Next difficulty: 3" in item for item in result.evidence_basis)
    assert any("Optimal time complexity" in item for item in result.evidence_basis)


def test_advance_reasoning():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Cloud Infrastructure")
    evaluation = make_eval(demonstrated_level=4)
    decision = make_decision(action=AdaptiveAction.ADVANCE, target_difficulty=2)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=3,
    )

    assert result.action == AdaptiveAction.ADVANCE
    assert "demonstrated sufficient evidence for Cloud Infrastructure" in result.reason
    assert "moving to another configured competency" in result.reason
    assert result.difficulty_change is None
    assert result.competency_name == "Cloud Infrastructure"
    assert any("Competency satisfied: Cloud Infrastructure" in item for item in result.evidence_basis)


def test_redirect_reasoning_with_off_topic_reason():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Concurrency")
    evaluation = make_eval(
        is_off_topic=True,
        off_topic_reason="Candidate discussed culinary recipes instead of threads",
    )
    decision = make_decision(action=AdaptiveAction.REDIRECT, target_difficulty=1)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=1,
    )

    assert result.action == AdaptiveAction.REDIRECT
    assert "Your response appeared off-topic" in result.reason
    assert "Candidate discussed culinary recipes instead of threads" in result.reason
    assert "redirect you back to the topic" in result.reason
    assert result.difficulty_change == 0
    assert any("Response marked off-topic" in item for item in result.evidence_basis)
    assert any("culinary recipes" in item for item in result.evidence_basis)


def test_redirect_reasoning_without_specific_off_topic_reason():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Concurrency")
    evaluation = make_eval(is_off_topic=True, off_topic_reason=None)
    decision = make_decision(action=AdaptiveAction.REDIRECT, target_difficulty=1)

    result = service.reason(
        decision=decision,
        evaluation=evaluation,
        competency=comp,
        current_difficulty=1,
    )

    assert result.action == AdaptiveAction.REDIRECT
    assert "Your response appeared off-topic" in result.reason
    assert "redirect you back to the topic" in result.reason
    assert result.difficulty_change == 0


def test_redirect_no_personality_judgment():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="API Design")
    evaluation = make_eval(
        is_off_topic=True,
        off_topic_reason="Candidate provided unrelated anecdotes",
    )
    decision = make_decision(action=AdaptiveAction.REDIRECT)

    result = service.reason(decision=decision, evaluation=evaluation, competency=comp)

    # Ensure no judgmental personality language is used
    forbidden_words = ["lazy", "dishonest", "unprepared", "attitude", "character", "evasive"]
    for word in forbidden_words:
        assert word not in result.reason.lower(), f"Forbidden word '{word}' found in reason"


def test_complete_does_not_suggest_another_question():
    service = FollowUpReasoningService()
    evaluation = make_eval(demonstrated_level=3)
    decision = make_decision(
        action=AdaptiveAction.COMPLETE,
        target_difficulty=None,
        based_on_turn=10,
    )

    result = service.reason(decision=decision, evaluation=evaluation)

    assert result.action == AdaptiveAction.COMPLETE
    assert "assessment is complete" in result.reason
    assert "next question" not in result.reason.lower()
    assert result.difficulty_change is None
    assert result.competency_name is None
    assert any("Turn number: 10" in item for item in result.evidence_basis)


# ---------------------------------------------------------------------------
# Quality & Boundary Properties
# ---------------------------------------------------------------------------

def test_reasoning_is_deterministic():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Testing")
    evaluation = make_eval(demonstrated_level=2, gaps=["boundary conditions"])
    decision = make_decision(action=AdaptiveAction.PROBE, target_difficulty=2)

    res1 = service.reason(decision, evaluation, comp, current_difficulty=2)
    res2 = service.reason(decision, evaluation, comp, current_difficulty=2)

    assert res1.model_dump() == res2.model_dump()


def test_reasoning_does_not_call_llm():
    # Verify that FollowUpReasoningService has no AI provider or LLM client
    service = FollowUpReasoningService()
    assert not hasattr(service, "provider")
    assert not hasattr(service, "client")
    assert not hasattr(service, "llm")


def test_reasoning_does_not_expose_hidden_chain_of_thought():
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Security")
    evaluation = make_eval(demonstrated_level=3, gaps=["OAuth2 token refresh"])
    decision = make_decision(action=AdaptiveAction.PROBE, target_difficulty=2)

    result = service.reason(decision, evaluation, comp, current_difficulty=2)

    forbidden_cot_markers = [
        "thought:",
        "<thought>",
        "scratchpad",
        "internal rationale",
        "hidden_thought",
        "chain of thought",
    ]
    for marker in forbidden_cot_markers:
        assert marker not in result.reason.lower()


# ---------------------------------------------------------------------------
# Integration with AdaptiveInterviewOrchestrator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_stores_follow_up_reasoning_in_state():
    comp_id = uuid4()
    comp = SimpleNamespace(id=comp_id, name="Algorithms")
    q = SimpleNamespace(id=uuid4(), difficulty_level=2, competency_id=comp_id, question_text="Explain heapsort.")

    # Create mock response service returning evaluation with a gap
    mock_eval = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate has superficial knowledge.",
        demonstrated_level=1,
        depth_score=2.0,
        relevance_score=3.5,
        technical_accuracy_score=2.0,
        confidence=0.85,
        strengths=["Mentioned binary trees"],
        gaps=["heapify complexity analysis"],
        is_off_topic=False,
    )
    mock_response_service = MagicMock()
    mock_response_service.evaluate_answer = AsyncMock(return_value=mock_eval)

    # Custom question selector returning next question
    next_q = SimpleNamespace(id=uuid4(), difficulty_level=2, competency_id=comp_id, question_text="What is the heapify time complexity?")

    async def mock_selector(**kwargs):
        return next_q

    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=mock_response_service,
        question_selector=mock_selector,
    )

    initial_state: InterviewGraphState = {
        "candidate_response": "Heapsort uses a tree to sort elements.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 1,
        "min_turns": 5,
        "max_turns": 10,
        "interview_status": "IN_PROGRESS",
    }

    result_state = await orchestrator.run_turn(initial_state)

    assert "follow_up_reasoning" in result_state
    follow_up: FollowUpReasoning = result_state["follow_up_reasoning"]
    assert isinstance(follow_up, FollowUpReasoning)
    assert follow_up.action == AdaptiveAction.PROBE
    assert "heapify complexity analysis" in follow_up.reason
    assert result_state["why_this_follow_up"] == follow_up.reason


# ---------------------------------------------------------------------------
# Three Specific Manual Scenarios
# ---------------------------------------------------------------------------

def test_manual_scenario_1_probe_with_gap():
    """Scenario 1: Candidate answer has gap -> PROBE with gap explanation."""
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Reliability Engineering")
    evaluation = make_eval(
        demonstrated_level=1,
        gaps=["handling production failures"],
    )
    decision = make_decision(action=AdaptiveAction.PROBE, target_difficulty=1)

    result = service.reason(decision, evaluation, competency=comp, current_difficulty=1)

    assert result.action == AdaptiveAction.PROBE
    assert "Your answer showed basic understanding, but did not provide enough evidence about handling production failures. The next question probes that gap." in result.reason
    assert result.difficulty_change == 0
    assert result.competency_name == "Reliability Engineering"


def test_manual_scenario_2_escalate_difficulty_progression():
    """Scenario 2: Candidate answer meets target level -> ESCALATE with difficulty progression."""
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="System Architecture")
    evaluation = make_eval(demonstrated_level=3, strengths=["Comprehensive trade-off evaluation"])
    decision = make_decision(action=AdaptiveAction.ESCALATE, target_difficulty=3)

    result = service.reason(decision, evaluation, competency=comp, current_difficulty=2)

    assert result.action == AdaptiveAction.ESCALATE
    assert "You demonstrated the target competency level for System Architecture at difficulty 2, so the interview is increasing the challenge to difficulty 3 to test the skill under a more demanding scenario." in result.reason
    assert result.difficulty_change == 1
    assert any("Previous difficulty: 2" in item for item in result.evidence_basis)
    assert any("Next difficulty: 3" in item for item in result.evidence_basis)


def test_manual_scenario_3_redirect_off_topic():
    """Scenario 3: Candidate answer is off-topic -> REDIRECT with neutral explanation."""
    service = FollowUpReasoningService()
    comp = SimpleNamespace(name="Microservices")
    evaluation = make_eval(
        is_off_topic=True,
        off_topic_reason="Candidate described chocolate cake recipe instead of API gateway patterns",
    )
    decision = make_decision(action=AdaptiveAction.REDIRECT, target_difficulty=2)

    result = service.reason(decision, evaluation, competency=comp, current_difficulty=2)

    assert result.action == AdaptiveAction.REDIRECT
    assert "Your response appeared off-topic and did not address the current question (Candidate described chocolate cake recipe instead of API gateway patterns), so the interview will redirect you back to the topic before continuing the assessment." in result.reason
    assert result.difficulty_change == 0
    assert any("chocolate cake recipe" in item for item in result.evidence_basis)
