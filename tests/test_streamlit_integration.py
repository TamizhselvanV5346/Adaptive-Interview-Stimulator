import io
from uuid import UUID, uuid4
import pytest
from pypdf import PdfReader

from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.response_evaluation import ResponseEvaluation
from app.evaluation.competency_scoring import CompetencyScoringService
from app.interview.adaptive_decision import AdaptiveDecisionEngine
from app.interview.conversation_recovery import ConversationRecoveryService
from app.interview.demo_data import (
    COMP_DISTRIBUTED_SYSTEMS_ID,
    COMP_INCIDENT_RELIABILITY_ID,
    COMP_SYSTEM_ARCHITECTURE_ID,
    DEMO_INTERVIEW_PROFILES,
    DEMO_QUESTIONS,
    InMemoryQuestionSelector,
)
from app.interview.follow_up_reasoning import FollowUpReasoningService
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import AdaptiveInterviewOrchestrator
from app.reporting.assessment_report import AssessmentReportService
from app.reporting.pdf_report import PDFReportGenerator


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_orchestrator():
    provider = MockProvider()
    response_service = ResponseIntelligenceService(provider=provider)
    decision_engine = AdaptiveDecisionEngine()
    reasoning_service = FollowUpReasoningService()
    recovery_service = ConversationRecoveryService()
    question_selector = InMemoryQuestionSelector(DEMO_QUESTIONS)

    return AdaptiveInterviewOrchestrator(
        response_service=response_service,
        decision_engine=decision_engine,
        reasoning_service=reasoning_service,
        recovery_service=recovery_service,
        question_selector=question_selector,
    )


# ---------------------------------------------------------------------------
# 1-3: Question Selector & Demo Data Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_memory_question_selector_exact_match():
    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    q = await selector(
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=2,
        used_question_ids=[],
    )
    assert q is not None
    assert q.competency_id == COMP_DISTRIBUTED_SYSTEMS_ID
    assert q.difficulty_level == 2


@pytest.mark.asyncio
async def test_in_memory_question_selector_excludes_used():
    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    q1 = await selector(
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=2,
        used_question_ids=[],
    )
    assert q1 is not None

    q2 = await selector(
        competency_id=COMP_DISTRIBUTED_SYSTEMS_ID,
        difficulty_level=2,
        used_question_ids=[q1.id],
    )
    assert q2 is not None
    assert q2.id != q1.id


def test_demo_interview_profiles_structure():
    assert len(DEMO_INTERVIEW_PROFILES) >= 3
    for name, prof in DEMO_INTERVIEW_PROFILES.items():
        assert "job_title" in prof
        assert "seniority" in prof
        assert "description" in prof
        assert len(prof["competencies"]) >= 3


# ---------------------------------------------------------------------------
# 4-7: Adaptive Loop & Why This Follow-Up Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weak_answer_triggers_probe(mock_orchestrator: AdaptiveInterviewOrchestrator):
    profile = list(DEMO_INTERVIEW_PROFILES.values())[0]
    comp = profile["competencies"][0]
    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    q = await selector(competency_id=comp.id, difficulty_level=2)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "I am not sure how to handle partitions and I have no experience with Raft.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": profile["competencies"],
        "used_question_ids": [q.id],
        "remaining_eligible_questions": True,
    }

    result = await mock_orchestrator.run_turn(state)

    assert result.get("action") == AdaptiveAction.PROBE
    assert result.get("why_this_follow_up") is not None
    assert "probe" in result.get("why_this_follow_up").lower()
    assert result.get("next_question") is not None


@pytest.mark.asyncio
async def test_strong_answer_triggers_escalate(mock_orchestrator: AdaptiveInterviewOrchestrator):
    profile = list(DEMO_INTERVIEW_PROFILES.values())[0]
    comp = profile["competencies"][0]
    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    q = await selector(competency_id=comp.id, difficulty_level=2)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": (
            "We implemented Raft consensus with leader election, quorum heartbeats, "
            "and idempotent Kafka consumers backed by distributed Redis caches and circuit breakers."
        ),
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": profile["competencies"],
        "used_question_ids": [q.id],
        "remaining_eligible_questions": True,
    }

    result = await mock_orchestrator.run_turn(state)

    assert result.get("action") == AdaptiveAction.ESCALATE
    assert result.get("next_difficulty") == 3
    assert result.get("why_this_follow_up") is not None
    assert "difficulty" in result.get("why_this_follow_up").lower()


@pytest.mark.asyncio
async def test_off_topic_biryani_triggers_redirect(mock_orchestrator: AdaptiveInterviewOrchestrator):
    profile = list(DEMO_INTERVIEW_PROFILES.values())[0]
    comp = profile["competencies"][0]
    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    q = await selector(competency_id=comp.id, difficulty_level=2)

    state: InterviewGraphState = {
        "session_id": uuid4(),
        "current_turn": 1,
        "min_turns": 8,
        "max_turns": 12,
        "candidate_response": "I cooked biryani yesterday.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 2,
        "interview_competencies": profile["competencies"],
        "used_question_ids": [q.id],
        "retry_count": 0,
        "remaining_eligible_questions": True,
    }

    result = await mock_orchestrator.run_turn(state)

    assert result.get("action") == AdaptiveAction.REDIRECT
    assert result.get("interview_status") == "REDIRECTED"
    assert result.get("redirect_message") is not None
    assert "stay with the current question" in result.get("redirect_message").lower()
    assert result.get("next_question") == q


# ---------------------------------------------------------------------------
# 8: Full 8+ Turn Interview Loop & PDF Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_8_turn_adaptive_interview_and_pdf_generation(mock_orchestrator: AdaptiveInterviewOrchestrator):
    profile = list(DEMO_INTERVIEW_PROFILES.values())[0]
    competencies = profile["competencies"]
    session_id = uuid4()
    candidate_id = uuid4()

    selector = InMemoryQuestionSelector(DEMO_QUESTIONS)
    current_comp = competencies[0]
    current_diff = 2
    current_q = await selector(competency_id=current_comp.id, difficulty_level=current_diff)
    used_q_ids = [current_q.id]
    evaluations: list[ResponseEvaluation] = []

    # Responses designed to test varied adaptation: Turn 1 strong, Turn 2 off-topic, Turn 2 retry weak, etc.
    turn_answers = [
        "We used Raft consensus with distributed state machines and idempotent token caches.",  # Strong -> ESCALATE (diff 3)
        "I cooked biryani yesterday.",  # Off-topic -> REDIRECT (same Q)
        "I don't know much about handling cluster partitions or split brain scenarios.",  # Retry Weak -> PROBE
        "We implemented Kafka partitioned streams with distributed consumers and circuit breakers.",  # Strong -> ADVANCE (comp 2)
        "We used write-through caching with Redis clusters and snowflake distributed IDs.",  # Strong -> ESCALATE (diff 3)
        "We configured Prometheus metrics, APM distributed tracing, and automated rollback canary.",  # Strong -> ADVANCE (comp 3)
        "I am not sure how error budgets and SLIs are calculated.",  # Weak -> PROBE
        "We ran blameless post-mortems using 5 Whys and automated chaos engineering tests.",  # Strong -> COMPLETE
    ]

    turn_count = 0
    max_loops = 12

    for ans in turn_answers:
        turn_count += 1
        state: InterviewGraphState = {
            "session_id": session_id,
            "current_turn": turn_count,
            "min_turns": 8,
            "max_turns": 12,
            "candidate_response": ans,
            "current_question": current_q,
            "current_competency": current_comp,
            "current_difficulty": current_diff,
            "interview_competencies": competencies,
            "used_question_ids": used_q_ids,
            "retry_count": 0,
            "remaining_eligible_questions": True,
        }

        res = await mock_orchestrator.run_turn(state)
        eval_obj = res.get("response_evaluation")
        if eval_obj:
            evaluations.append(eval_obj)

        action = res.get("action")
        why = res.get("why_this_follow_up")
        assert why is not None and len(why) > 0

        if res.get("interview_status") == "REDIRECTED":
            # Off-topic redirect: Keep current question for next turn
            continue

        if res.get("interview_status") == "COMPLETED" or turn_count >= 8:
            break

        if res.get("next_question"):
            current_q = res["next_question"]
            used_q_ids.append(current_q.id)
        if res.get("next_competency"):
            current_comp = res["next_competency"]
        if res.get("next_difficulty"):
            current_diff = res["next_difficulty"]

    # Final Competency Scoring
    scoring_svc = CompetencyScoringService()
    final_assessment = scoring_svc.score_interview(
        session_id=session_id,
        interview_competencies=competencies,
        evaluations=evaluations,
        completed=True,
    )

    assert final_assessment.completed is True
    assert final_assessment.overall_score > 0.0
    assert len(final_assessment.competency_scores) == len(competencies)

    # Assessment Report Generation
    report_svc = AssessmentReportService()
    report = report_svc.generate_report(
        assessment=final_assessment,
        candidate_id=candidate_id,
        session_title=profile["job_title"],
    )
    assert report.overall_score == final_assessment.overall_score
    assert len(report.competency_reports) == 3

    # PDF Generation & Verification
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000

    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Adaptive Interview Assessment" in pdf_text
    assert "Overall Score" in pdf_text
    assert "Competency Score Breakdown" in pdf_text
