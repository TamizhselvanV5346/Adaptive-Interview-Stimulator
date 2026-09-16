from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.adaptive_decision import AdaptiveDecisionEngine


# ---------------------------------------------------------------------------
# Helpers for mock domain entities
# ---------------------------------------------------------------------------

def make_evaluation(
    *,
    competency_id: UUID | None = None,
    demonstrated_level: int = 3,
    relevance_score: float = 4.0,
    depth_score: float = 3.5,
    technical_accuracy_score: float = 4.0,
    confidence: float = 0.9,
    is_off_topic: bool = False,
    off_topic_reason: str | None = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        competency_id=competency_id or uuid4(),
        evidence_summary="Candidate demonstrated clear evidence of problem solving.",
        strengths=["Clear technical communication"],
        gaps=["Could provide more real-world examples"],
        relevance_score=relevance_score,
        depth_score=depth_score,
        technical_accuracy_score=technical_accuracy_score,
        confidence=confidence,
        demonstrated_level=demonstrated_level,
        is_off_topic=is_off_topic,
        off_topic_reason=off_topic_reason,
    )


def make_competency(
    comp_id: UUID | None = None,
    name: str = "Algorithms",
    org_id: UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=comp_id or uuid4(),
        name=name,
        organization_id=org_id or uuid4(),
        description="Core algorithmic problem solving",
    )


def make_question(
    diff_level: int = 2,
    comp_id: UUID | None = None,
    org_id: UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        difficulty_level=diff_level,
        competency_id=comp_id or uuid4(),
        organization_id=org_id or uuid4(),
        question_text="Sample interview question text",
    )


def make_interview_competency(
    comp_id: UUID,
    target_level: int = 3,
    weight: float = 1.0,
    display_order: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        competency_id=comp_id,
        target_level=target_level,
        weight=weight,
        display_order=display_order,
    )


# ---------------------------------------------------------------------------
# 1-4: Contract Validation Tests
# ---------------------------------------------------------------------------

def test_valid_decision_contract():
    """1. Valid decision contract instantiates correctly."""
    comp_id = uuid4()
    decision = AdaptiveDecision(
        action=AdaptiveAction.PROBE,
        reason="Need additional depth on memory optimization.",
        target_competency_id=comp_id,
        target_difficulty=3,
        confidence=0.92,
        based_on_turn=2,
    )
    assert decision.action == AdaptiveAction.PROBE
    assert decision.target_competency_id == comp_id
    assert decision.target_difficulty == 3
    assert decision.confidence == 0.92
    assert decision.based_on_turn == 2


def test_blank_reason_rejected():
    """2. Blank or whitespace reason is rejected."""
    comp_id = uuid4()
    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="   \n\t  ",
            target_competency_id=comp_id,
            target_difficulty=3,
            confidence=0.9,
            based_on_turn=1,
        )


def test_invalid_confidence_rejected():
    """3. Confidence must be between 0.0 and 1.0."""
    comp_id = uuid4()
    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            target_competency_id=comp_id,
            target_difficulty=3,
            confidence=-0.1,
            based_on_turn=1,
        )

    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            target_competency_id=comp_id,
            target_difficulty=3,
            confidence=1.1,
            based_on_turn=1,
        )


def test_invalid_difficulty_rejected():
    """4. Target difficulty must be integer in [1, 5] when provided."""
    comp_id = uuid4()
    # Below 1
    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            target_competency_id=comp_id,
            target_difficulty=0,
            confidence=0.8,
            based_on_turn=1,
        )

    # Above 5
    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            target_competency_id=comp_id,
            target_difficulty=6,
            confidence=0.8,
            based_on_turn=1,
        )

    # Rejection of boolean
    with pytest.raises(ValidationError):
        AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason="Valid reason",
            target_competency_id=comp_id,
            target_difficulty=True,
            confidence=0.8,
            based_on_turn=1,
        )


# ---------------------------------------------------------------------------
# 5-7: Off-Topic and Weak Evidence Tests
# ---------------------------------------------------------------------------

def test_off_topic_redirect():
    """5. Off-topic answer triggers REDIRECT with explanatory reason."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    eval_obj = make_evaluation(
        competency_id=comp.id,
        is_off_topic=True,
        off_topic_reason="Candidate discussed favorite programming language instead of debugging incident.",
    )

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.REDIRECT
    assert "off-topic" in decision.reason.lower()
    assert decision.target_competency_id == comp.id


def test_weak_evidence_probe():
    """6. Weak evidence (demonstrated_level < target_level) triggers PROBE."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    eval_obj = make_evaluation(
        competency_id=comp.id,
        demonstrated_level=1,  # Below target 3
    )

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.PROBE
    assert "probing the same competency" in decision.reason.lower()


def test_weak_evidence_targets_current_competency():
    """7. PROBE targets the same competency to gather deeper evidence."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    other_comp = make_competency(name="System Design")
    ic1 = make_interview_competency(comp.id, target_level=4)
    ic2 = make_interview_competency(other_comp.id, target_level=3)
    question = make_question(diff_level=3, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=2)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic1, ic2],
        current_question=question,
        current_turn=1,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.PROBE
    assert decision.target_competency_id == comp.id
    assert decision.target_difficulty == 3


# ---------------------------------------------------------------------------
# 8-10: Strong Answer and Difficulty Escalation Tests
# ---------------------------------------------------------------------------

def test_strong_answer_escalate():
    """8. Strong answer meeting or exceeding target level escalates difficulty."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=3)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.ESCALATE
    assert decision.target_competency_id == comp.id
    assert decision.target_difficulty == 3  # 2 + 1


def test_difficulty_increments_correctly():
    """9. Difficulty increments by exactly one level on escalation."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=1, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=1,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.ESCALATE
    assert decision.target_difficulty == 2


def test_difficulty_capped_at_5():
    """10. Difficulty never escalates past 5."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency(name="Concurrency")
    other_comp = make_competency(name="Databases")
    ic1 = make_interview_competency(comp.id, target_level=4)
    ic2 = make_interview_competency(other_comp.id, target_level=3)

    # Current difficulty already at maximum 5
    question = make_question(diff_level=5, comp_id=comp.id)
    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=5)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic1, ic2],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
    )

    # Must NOT escalate to 6; advances to next competency
    assert decision.action == AdaptiveAction.ADVANCE
    assert decision.target_difficulty <= 5
    assert decision.target_competency_id == other_comp.id


# ---------------------------------------------------------------------------
# 11-14: Competency Advancement and Ordering Tests
# ---------------------------------------------------------------------------

def test_satisfied_competency_advance():
    """11. When current competency is satisfied at max difficulty, ADVANCE to next."""
    engine = AdaptiveDecisionEngine()
    comp1 = make_competency(name="Algorithms")
    comp2 = make_competency(name="System Design")

    ic1 = make_interview_competency(comp1.id, target_level=3, weight=1.0, display_order=1)
    ic2 = make_interview_competency(comp2.id, target_level=4, weight=2.0, display_order=2)

    question = make_question(diff_level=5, comp_id=comp1.id)
    eval_obj = make_evaluation(competency_id=comp1.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp1,
        interview_competencies=[ic1, ic2],
        current_question=question,
        current_turn=4,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.ADVANCE
    assert decision.target_competency_id == comp2.id


def test_another_unsatisfied_competency_selected():
    """12. Next competency selected is another configured competency from interview."""
    engine = AdaptiveDecisionEngine()
    comp1 = make_competency(name="Comp1")
    comp2 = make_competency(name="Comp2")
    comp3 = make_competency(name="Comp3")

    ic1 = make_interview_competency(comp1.id, target_level=3, weight=1.0, display_order=1)
    ic2 = make_interview_competency(comp2.id, target_level=3, weight=2.0, display_order=2)
    ic3 = make_interview_competency(comp3.id, target_level=3, weight=1.5, display_order=3)

    question = make_question(diff_level=5, comp_id=comp1.id)
    eval_obj = make_evaluation(competency_id=comp1.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp1,
        interview_competencies=[ic1, ic2, ic3],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.ADVANCE
    assert decision.target_competency_id in {comp2.id, comp3.id}


def test_competency_ordering_respected():
    """13. Competencies are ordered by weight descending, then display_order ascending."""
    engine = AdaptiveDecisionEngine()
    comp1 = make_competency(name="Comp1")
    comp2 = make_competency(name="Comp2")  # weight 1.0, display 2
    comp3 = make_competency(name="Comp3")  # weight 3.0, display 3 (higher weight!)

    ic1 = make_interview_competency(comp1.id, target_level=3, weight=1.0, display_order=1)
    ic2 = make_interview_competency(comp2.id, target_level=3, weight=1.0, display_order=2)
    ic3 = make_interview_competency(comp3.id, target_level=3, weight=3.0, display_order=3)

    question = make_question(diff_level=5, comp_id=comp1.id)
    eval_obj = make_evaluation(competency_id=comp1.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp1,
        interview_competencies=[ic1, ic2, ic3],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
    )

    # comp3 has weight 3.0, so it must be preferred over comp2
    assert decision.action == AdaptiveAction.ADVANCE
    assert decision.target_competency_id == comp3.id


def test_competency_target_level_respected():
    """14. Competency target level from interview configuration governs probe vs escalate."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()

    # High target level: 5
    ic = make_interview_competency(comp.id, target_level=5)
    question = make_question(diff_level=3, comp_id=comp.id)

    # Demonstrated 3: met question difficulty, but below target 5!
    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=3)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    # Since target is 5 and demonstrated is 3, it should PROBE rather than complete/escalate past target
    assert decision.action == AdaptiveAction.PROBE


# ---------------------------------------------------------------------------
# 15-18: Turn Limits and Completion Behavior Tests
# ---------------------------------------------------------------------------

def test_minimum_turn_completion_behavior():
    """15. Satisfied competencies trigger COMPLETE once min_turns is satisfied."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=5, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=8,  # Exactly min_turns
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.COMPLETE
    assert decision.target_difficulty is None
    assert "minimum turn requirement satisfied" in decision.reason.lower()


def test_maximum_turn_completion_behavior():
    """16. Reaching max_turns triggers COMPLETE immediately."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=1)  # Even with weak answer!

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=12,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.COMPLETE
    assert decision.target_difficulty is None
    assert "maximum" in decision.reason.lower()


def test_max_turns_prevents_further_question():
    """17. Max turns prevents further questioning regardless of evaluation strength."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    strong_eval = make_evaluation(competency_id=comp.id, demonstrated_level=5)

    decision = engine.decide(
        evaluation=strong_eval,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=12,
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.COMPLETE
    assert decision.target_difficulty is None


def test_no_cross_organization_competency_selection():
    """18. Only competencies in the supplied interview definition are selected."""
    engine = AdaptiveDecisionEngine()
    org_id = uuid4()
    foreign_org_id = uuid4()

    comp1 = make_competency(org_id=org_id)
    comp2 = make_competency(org_id=org_id)

    ic1 = make_interview_competency(comp1.id, target_level=3)
    ic2 = make_interview_competency(comp2.id, target_level=3)

    question = make_question(diff_level=5, comp_id=comp1.id, org_id=org_id)
    eval_obj = make_evaluation(competency_id=comp1.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp1,
        interview_competencies=[ic1, ic2],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
    )

    # Must choose comp2, never a foreign competency
    assert decision.action == AdaptiveAction.ADVANCE
    assert decision.target_competency_id == comp2.id


# ---------------------------------------------------------------------------
# 19-20: Determinism and Question Text Separation Tests
# ---------------------------------------------------------------------------

def test_decision_is_deterministic_for_identical_input():
    """19. Decision engine returns identical decision object for identical inputs."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)
    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=3)

    dec1 = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    dec2 = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    assert dec1.model_dump() == dec2.model_dump()


def test_decision_never_generates_question_text():
    """20. AdaptiveDecision contains only decision metadata and never generates question text."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)
    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=3)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=2,
        min_turns=8,
        max_turns=12,
    )

    dump = decision.model_dump()
    assert "question_text" not in dump
    assert "next_question" not in dump
    assert "question" not in dump


# ---------------------------------------------------------------------------
# 21-25: Important Edge Case Tests
# ---------------------------------------------------------------------------

def test_strong_answer_on_difficulty_5_does_not_escalate_to_6():
    """21. Edge Case A: Strong answer on difficulty 5 must not produce difficulty 6."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=5, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=5)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
    )

    assert decision.target_difficulty != 6
    if decision.target_difficulty is not None:
        assert decision.target_difficulty <= 5


def test_off_topic_at_minimum_turn_still_redirects():
    """22. Edge Case B: Off-topic answer at minimum turn still triggers redirect."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)

    eval_obj = make_evaluation(
        competency_id=comp.id,
        is_off_topic=True,
        off_topic_reason="Candidate discussed personal hobbies.",
    )

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=8,  # Exactly min_turns, but max_turns is 12
        min_turns=8,
        max_turns=12,
    )

    assert decision.action == AdaptiveAction.REDIRECT


def test_single_competency_satisfied_does_not_invent_competency():
    """23. Edge Case D: When only 1 competency exists, ADVANCE does not invent another."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=5, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=3,  # < min_turns 8
        min_turns=8,
        max_turns=12,
    )

    # Must stay on comp, never invent a non-existent competency ID
    assert decision.target_competency_id == comp.id
    assert decision.action in (AdaptiveAction.PROBE, AdaptiveAction.ESCALATE)


def test_all_competencies_satisfied_before_min_turns_continues_safely():
    """24. Edge Case E: All competencies satisfied before min_turns continues safely."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=5, comp_id=comp.id)

    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=4)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=4,  # Before min_turns 8
        min_turns=8,
        max_turns=12,
    )

    assert decision.action != AdaptiveAction.COMPLETE
    assert decision.target_competency_id == comp.id


def test_no_remaining_questions_triggers_complete():
    """25. Edge Case F: No remaining eligible questions triggers COMPLETE."""
    engine = AdaptiveDecisionEngine()
    comp = make_competency()
    ic = make_interview_competency(comp.id, target_level=3)
    question = make_question(diff_level=2, comp_id=comp.id)
    eval_obj = make_evaluation(competency_id=comp.id, demonstrated_level=3)

    decision = engine.decide(
        evaluation=eval_obj,
        competency=comp,
        interview_competencies=[ic],
        current_question=question,
        current_turn=3,
        min_turns=8,
        max_turns=12,
        remaining_eligible_questions=False,
    )

    assert decision.action == AdaptiveAction.COMPLETE
    assert decision.target_difficulty is None
    assert "no further eligible questions" in decision.reason.lower()
