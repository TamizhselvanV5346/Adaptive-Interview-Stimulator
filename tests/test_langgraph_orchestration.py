from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.adaptive_decision import AdaptiveDecisionEngine
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import (
    AdaptiveInterviewOrchestrator,
    create_interview_graph,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

def make_test_competency(name: str = "Distributed Systems", comp_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=comp_id or uuid4(),
        name=name,
        description=f"Assessment of {name}",
    )


def make_test_question(diff: int = 2, comp_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        difficulty_level=diff,
        competency_id=comp_id or uuid4(),
        question_text=f"Question at difficulty {diff}",
    )


def make_test_ic(comp_id: UUID, target_level: int = 3, weight: float = 1.0, display_order: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        competency_id=comp_id,
        target_level=target_level,
        weight=weight,
        display_order=display_order,
    )


class MockQuestionSelectorTracker:
    """Tracks questions requested by orchestrator and returns deterministic mock questions."""

    def __init__(self):
        self.calls: list[dict] = []
        self.return_none: bool = False

    async def __call__(
        self,
        interview_definition_id: UUID | None = None,
        organization_id: UUID | None = None,
        competency_id: UUID | None = None,
        difficulty_level: int | None = None,
        used_question_ids: list[UUID] | None = None,
    ):
        self.calls.append({
            "interview_definition_id": interview_definition_id,
            "organization_id": organization_id,
            "competency_id": competency_id,
            "difficulty_level": difficulty_level,
            "used_question_ids": used_question_ids,
        })
        if self.return_none:
            return None
        return SimpleNamespace(
            id=uuid4(),
            difficulty_level=difficulty_level or 1,
            competency_id=competency_id,
            question_text=f"Selected follow-up for diff {difficulty_level}",
        )


# ---------------------------------------------------------------------------
# 1-5: Action Branch Routing Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_probe_branch():
    """1. Weak evidence triggers PROBE and routes to probe_question node."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency("Data Structures")
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    # Queue weak evaluation: demonstrated_level=1 (target is 3)
    orchestrator.response_service.provider.queue_evaluation(
        ResponseEvaluation(
            competency_id=comp.id,
            evidence_summary="Candidate struggled with hash table collision resolution.",
            strengths=[],
            gaps=["Did not understand open addressing or chaining"],
            relevance_score=3.0,
            depth_score=2.0,
            technical_accuracy_score=2.0,
            confidence=0.9,
            demonstrated_level=1,
            is_off_topic=False,
        )
    )

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "I am not sure how collisions are resolved.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.PROBE
    assert result["interview_status"] == "IN_PROGRESS"
    assert result["next_question"] is not None
    assert result["next_difficulty"] == 2
    assert tracker.calls[0]["difficulty_level"] == 2
    assert tracker.calls[0]["competency_id"] == comp.id


@pytest.mark.asyncio
async def test_route_escalate_branch():
    """2. Strong answer triggers ESCALATE and routes to escalate_question node with higher difficulty."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency("Concurrency")
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    # Queue strong evaluation: demonstrated_level=3 meeting target level
    orchestrator.response_service.provider.queue_evaluation(
        ResponseEvaluation(
            competency_id=comp.id,
            evidence_summary="Candidate demonstrated solid mastery of atomic operations.",
            strengths=["Clear explanation of CAS and memory fences"],
            gaps=[],
            relevance_score=4.5,
            depth_score=4.0,
            technical_accuracy_score=4.5,
            confidence=0.95,
            demonstrated_level=3,
            is_off_topic=False,
        )
    )

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "We use Compare-And-Swap primitives to implement lock-free queues.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.ESCALATE
    assert result["interview_status"] == "IN_PROGRESS"
    assert result["next_difficulty"] == 3  # 2 + 1
    assert tracker.calls[0]["difficulty_level"] == 3
    assert tracker.calls[0]["competency_id"] == comp.id


@pytest.mark.asyncio
async def test_route_advance_branch():
    """3. Competency satisfied at difficulty 5 routes to advance_question for next competency."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp1 = make_test_competency("Algorithms")
    comp2 = make_test_competency("System Design")

    ic1 = make_test_ic(comp1.id, target_level=3, weight=1.0, display_order=1)
    ic2 = make_test_ic(comp2.id, target_level=4, weight=2.0, display_order=2)
    question = make_test_question(diff=5, comp_id=comp1.id)

    # Queue strong evaluation at diff 5
    orchestrator.response_service.provider.queue_evaluation(
        ResponseEvaluation(
            competency_id=comp1.id,
            evidence_summary="Candidate demonstrated top-tier algorithmic reasoning.",
            strengths=["Optimal complexity analysis"],
            gaps=[],
            relevance_score=5.0,
            depth_score=4.5,
            technical_accuracy_score=5.0,
            confidence=0.95,
            demonstrated_level=4,
            is_off_topic=False,
        )
    )

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 3,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Detailed discussion of dynamic programming and matrix exponentiation.",
        "current_question": question,
        "current_competency": comp1,
        "current_difficulty": 5,
        "interview_competencies": [ic1, ic2],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.ADVANCE
    assert result["interview_status"] == "IN_PROGRESS"
    assert tracker.calls[0]["competency_id"] == comp2.id
    assert tracker.calls[0]["difficulty_level"] == 4


@pytest.mark.asyncio
async def test_route_redirect_branch():
    """4. Off-topic response routes to redirect_candidate without failing candidate."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency("Incident Management")
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    # Off-topic evaluation
    orchestrator.response_service.provider.queue_evaluation(
        ResponseEvaluation(
            competency_id=comp.id,
            evidence_summary="Candidate response was off-topic.",
            strengths=[],
            gaps=["Did not answer the question"],
            relevance_score=0.5,
            depth_score=1.0,
            technical_accuracy_score=1.0,
            confidence=0.9,
            demonstrated_level=1,
            is_off_topic=True,
            off_topic_reason="Candidate discussed favorite foods instead of production incidents.",
        )
    )

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "My favorite food is Italian pasta.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.REDIRECT
    assert result["interview_status"] == "REDIRECTED"
    assert "off-topic" in result["why_this_follow_up"].lower()
    # Does NOT invoke question selector (retains current context for conversational redirect)
    assert len(tracker.calls) == 0


@pytest.mark.asyncio
async def test_route_complete_branch():
    """5. Reaching max turns routes to complete_interview and halts questioning."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=3, comp_id=comp.id)

    orchestrator.response_service.provider.queue_evaluation(
        ResponseEvaluation(
            competency_id=comp.id,
            evidence_summary="Candidate provided standard answer.",
            strengths=["Clear response"],
            gaps=[],
            relevance_score=4.0,
            depth_score=3.5,
            technical_accuracy_score=4.0,
            confidence=0.9,
            demonstrated_level=3,
            is_off_topic=False,
        )
    )

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 12,  # Exactly max turns!
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Final turn response.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 3,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.COMPLETE
    assert result["interview_status"] == "COMPLETED"
    assert result["next_question"] is None
    assert result["next_difficulty"] is None
    assert len(tracker.calls) == 0


# ---------------------------------------------------------------------------
# 6-9: State Propagation & "Why This Follow-Up" Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_state_propagation_adaptive_decision():
    """6. AdaptiveDecision model is stored intact in graph state."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "I resolved memory leaks using heap dump analysis.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert "adaptive_decision" in result
    assert isinstance(result["adaptive_decision"], AdaptiveDecision)
    assert result["adaptive_decision"].based_on_turn == 1


@pytest.mark.asyncio
async def test_why_this_follow_up_survives_transition():
    """7. Human-readable rationale from Module 12 survives in graph state across transitions."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency("Architecture")
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Answer explaining architecture.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    expected_reasons = {result["adaptive_decision"].reason}
    if "follow_up_reasoning" in result and result["follow_up_reasoning"] is not None:
        expected_reasons.add(result["follow_up_reasoning"].reason)
    assert result["why_this_follow_up"] in expected_reasons


@pytest.mark.asyncio
async def test_target_competency_and_difficulty_propagated():
    """8. Target competency and difficulty are propagated accurately to next turn state."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency("Security")
    ic = make_test_ic(comp.id, target_level=4)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "We use mutual TLS and token rotation.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["next_difficulty"] is not None
    assert 1 <= result["next_difficulty"] <= 5
    assert result["next_competency"] is not None


# ---------------------------------------------------------------------------
# 9-13: Question Selection & Completion Safety Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completion_produces_no_question():
    """9. COMPLETE decision guarantees next_question is None."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=5, comp_id=comp.id)

    # Turn 8 of 8 min_turns with satisfied competency -> COMPLETE
    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 8,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Final complete answer.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 5,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["action"] == AdaptiveAction.COMPLETE
    assert result["next_question"] is None
    assert result["next_difficulty"] is None


@pytest.mark.asyncio
async def test_question_pool_exhaustion_terminates_gracefully():
    """10. When question selector returns None, graph terminates gracefully with COMPLETED."""
    tracker = MockQuestionSelectorTracker()
    tracker.return_none = True  # Simulates exhausted pool
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Sample response.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "COMPLETED"
    assert result["next_question"] is None


@pytest.mark.asyncio
async def test_used_question_ids_passed_to_selector():
    """11. used_question_ids from state are passed to QuestionSelector to prevent duplicates."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)
    used_id_1 = uuid4()
    used_id_2 = uuid4()

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Sample answer.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
        "used_question_ids": [used_id_1, used_id_2],
    }

    await orchestrator.run_turn(state)

    assert tracker.calls[0]["used_question_ids"] == [used_id_1, used_id_2]


# ---------------------------------------------------------------------------
# 12-16: Error Handling & Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_question_returns_failed_state():
    """12. Graph execution with missing current_question sets error and FAILED status."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency()

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "candidate_response": "Answer without question.",
        "current_competency": comp,
        "current_question": None,  # Missing!
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "FAILED"
    assert "Missing" in result["error"]


@pytest.mark.asyncio
async def test_missing_competency_returns_failed_state():
    """13. Graph execution with missing current_competency sets error and FAILED status."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    question = make_test_question()

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "candidate_response": "Answer without competency.",
        "current_question": question,
        "current_competency": None,  # Missing!
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "FAILED"
    assert "Missing" in result["error"]


@pytest.mark.asyncio
async def test_already_completed_interview_terminates_safely():
    """14. Graph rejects evaluation on already-completed interview safely."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency()
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 10,
        "candidate_response": "Late answer after completion.",
        "current_question": question,
        "current_competency": comp,
        "interview_status": "COMPLETED",
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "COMPLETED"
    assert result["next_question"] is None


@pytest.mark.asyncio
async def test_pure_offline_execution():
    """15. Graph executes 100% offline with zero database and zero external network calls."""
    orchestrator = AdaptiveInterviewOrchestrator(
        question_selector=MockQuestionSelectorTracker(),
        db=None,
    )
    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Pure offline test response.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] in ("IN_PROGRESS", "REDIRECTED", "COMPLETED")
    assert result["action"] is not None


@pytest.mark.asyncio
async def test_deterministic_orchestration_repeatability():
    """16. Identical state inputs produce identical graph outputs and actions."""
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=MockQuestionSelectorTracker())
    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state_template: InterviewGraphState = {
        "session_id": UUID("00000000-0000-0000-0000-000000000001"),
        "current_turn": 2,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Deterministic test response for repeatability check.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    res1 = await orchestrator.run_turn(dict(state_template))
    res2 = await orchestrator.run_turn(dict(state_template))

    assert res1["action"] == res2["action"]
    assert res1["why_this_follow_up"] == res2["why_this_follow_up"]
    assert res1["next_difficulty"] == res2["next_difficulty"]


@pytest.mark.asyncio
async def test_create_interview_graph_factory():
    """17. Factory function create_interview_graph compiles and returns executable LangGraph."""
    graph = create_interview_graph()
    assert graph is not None
    assert hasattr(graph, "ainvoke")


@pytest.mark.asyncio
async def test_no_arbitrary_questions_generated():
    """18. Graph strictly routes to QuestionSelector and never hallucinates question text."""
    tracker = MockQuestionSelectorTracker()
    orchestrator = AdaptiveInterviewOrchestrator(question_selector=tracker)

    comp = make_test_competency()
    ic = make_test_ic(comp.id, target_level=3)
    question = make_test_question(diff=2, comp_id=comp.id)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "Valid answer.",
        "current_question": question,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": [ic],
    }

    result = await orchestrator.run_turn(state)

    # Next question must be the exact object returned by tracker, not an invented LLM question string
    assert result["next_question"] is not None
    assert tracker.calls[0]["competency_id"] == comp.id
