from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain.competency_scoring import CompetencyScore, FinalAssessment
from app.domain.response_evaluation import ResponseEvaluation
from app.evaluation.competency_scoring import CompetencyScoringService


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_eval(
    competency_id: UUID,
    demonstrated_level: int = 3,
    confidence: float = 0.9,
    strengths: list[str] | None = None,
    gaps: list[str] | None = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        competency_id=competency_id,
        evidence_summary="Candidate demonstrated solid domain understanding.",
        demonstrated_level=demonstrated_level,
        depth_score=3.5,
        relevance_score=4.0,
        technical_accuracy_score=3.5,
        confidence=confidence,
        strengths=strengths or ["Clear architectural explanation"],
        gaps=gaps or [],
        is_off_topic=False,
    )


# ---------------------------------------------------------------------------
# Unit Tests: CompetencyScore & FinalAssessment Validation
# ---------------------------------------------------------------------------

def test_valid_competency_score():
    cid = uuid4()
    score = CompetencyScore(
        competency_id=cid,
        competency_name="Distributed Systems",
        target_level=4,
        demonstrated_level=3.5,
        score=70.0,
        weight=2.0,
        evidence_count=2,
        strengths=["Raft consensus protocol"],
        gaps=["Split-brain recovery"],
        confidence=0.88,
    )
    assert score.competency_id == cid
    assert score.competency_name == "Distributed Systems"
    assert score.target_level == 4
    assert score.demonstrated_level == 3.5
    assert score.score == 70.0
    assert score.weight == 2.0
    assert score.evidence_count == 2
    assert score.confidence == 0.88


def test_score_bounds_validation():
    cid = uuid4()
    # Score must be 0-100
    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=3.0,
            score=-1.0,
        )

    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=3.0,
            score=101.0,
        )


def test_demonstrated_level_bounds_validation():
    cid = uuid4()
    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=-0.5,
            score=50.0,
        )

    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=5.5,
            score=100.0,
        )


def test_confidence_bounds_validation():
    cid = uuid4()
    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=3.0,
            score=60.0,
            confidence=1.5,
        )

    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="Valid Name",
            target_level=3,
            demonstrated_level=3.0,
            score=60.0,
            confidence=-0.1,
        )


def test_competency_name_non_blank():
    cid = uuid4()
    with pytest.raises(ValidationError):
        CompetencyScore(
            competency_id=cid,
            competency_name="   ",
            target_level=3,
            demonstrated_level=3.0,
            score=60.0,
        )


def test_final_assessment_contract():
    sid = uuid4()
    cid = uuid4()
    score = CompetencyScore(
        competency_id=cid,
        competency_name="API Design",
        target_level=3,
        demonstrated_level=3.0,
        score=60.0,
    )
    assessment = FinalAssessment(
        session_id=sid,
        competency_scores=[score],
        overall_score=60.0,
        total_evidence_count=1,
        completed=True,
    )
    assert assessment.session_id == sid
    assert len(assessment.competency_scores) == 1
    assert assessment.overall_score == 60.0
    assert assessment.completed is True


# ---------------------------------------------------------------------------
# Unit Tests: CompetencyScoringService Behavior
# ---------------------------------------------------------------------------

def test_empty_evidence_produces_zero_score():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Incident Response", target_level=3, weight=1.0)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[],
    )

    assert len(result.competency_scores) == 1
    comp_score = result.competency_scores[0]
    assert comp_score.demonstrated_level == 0.0
    assert comp_score.score == 0.0
    assert comp_score.evidence_count == 0
    assert comp_score.confidence == 0.0
    assert comp_score.strengths == []
    assert comp_score.gaps == []
    assert result.overall_score == 0.0
    assert result.total_evidence_count == 0


def test_single_evaluation_scoring():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Testing & Quality", target_level=3, weight=1.0)
    evaluation = make_eval(competency_id=cid, demonstrated_level=4, confidence=0.85)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[evaluation],
    )

    assert result.overall_score == 80.0
    score = result.competency_scores[0]
    assert score.demonstrated_level == 4.0
    assert score.score == 80.0
    assert score.evidence_count == 1
    assert score.confidence == 0.85


def test_multiple_evaluations_same_competency():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Database Systems", target_level=3, weight=1.0)
    eval1 = make_eval(competency_id=cid, demonstrated_level=2, confidence=0.8)
    eval2 = make_eval(competency_id=cid, demonstrated_level=4, confidence=0.9)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[eval1, eval2],
    )

    score = result.competency_scores[0]
    # Average = (2 + 4) / 2 = 3.0 -> Score = 60.0
    assert score.demonstrated_level == 3.0
    assert score.score == 60.0
    assert score.evidence_count == 2
    assert score.confidence == 0.85


def test_deterministic_aggregation_repeatability():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Data Structures", target_level=3, weight=1.0)
    evals = [
        make_eval(competency_id=cid, demonstrated_level=3),
        make_eval(competency_id=cid, demonstrated_level=5),
    ]

    res1 = service.score_interview(session_id=sid, interview_competencies=[ic], evaluations=evals)
    res2 = service.score_interview(session_id=sid, interview_competencies=[ic], evaluations=evals)

    assert res1.model_dump() == res2.model_dump()


def test_strength_aggregation():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Networking", target_level=3, weight=1.0)
    eval1 = make_eval(competency_id=cid, strengths=["TCP three-way handshake", "TLS termination"])
    eval2 = make_eval(competency_id=cid, strengths=["HTTP/2 multiplexing"])

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[eval1, eval2],
    )

    score = result.competency_scores[0]
    assert len(score.strengths) == 3
    assert "TCP three-way handshake" in score.strengths
    assert "TLS termination" in score.strengths
    assert "HTTP/2 multiplexing" in score.strengths


def test_gap_aggregation():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Security", target_level=4, weight=1.0)
    eval1 = make_eval(competency_id=cid, gaps=["XSS prevention mechanisms"])
    eval2 = make_eval(competency_id=cid, gaps=["CSRF token rotation under microservices"])

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[eval1, eval2],
    )

    score = result.competency_scores[0]
    assert len(score.gaps) == 2
    assert "XSS prevention mechanisms" in score.gaps
    assert "CSRF token rotation under microservices" in score.gaps


def test_duplicate_evidence_deduplication():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Observability", target_level=3, weight=1.0)
    # Duplicate strength and gap across turns
    eval1 = make_eval(competency_id=cid, strengths=["Prometheus metrics"], gaps=["Distributed tracing"])
    eval2 = make_eval(competency_id=cid, strengths=["Prometheus metrics", "Log aggregation"], gaps=["Distributed tracing"])

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic],
        evaluations=[eval1, eval2],
    )

    score = result.competency_scores[0]
    assert score.strengths == ["Prometheus metrics", "Log aggregation"]
    assert score.gaps == ["Distributed tracing"]


def test_weighted_overall_score():
    service = CompetencyScoringService()
    sid = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    ic1 = SimpleNamespace(competency_id=c1, name="Technical Mastery", target_level=4, weight=60.0)
    ic2 = SimpleNamespace(competency_id=c2, name="Communication", target_level=3, weight=40.0)

    # c1: level 4 -> score 80
    eval1 = make_eval(competency_id=c1, demonstrated_level=4)
    # c2: level 3 -> score 60
    eval2 = make_eval(competency_id=c2, demonstrated_level=3)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic1, ic2],
        evaluations=[eval1, eval2],
    )

    # Overall = (80 * 0.6) + (60 * 0.4) = 48 + 24 = 72.0
    assert result.overall_score == 72.0


def test_weight_normalization():
    service = CompetencyScoringService()
    sid = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    # Weights do not sum to 100 (e.g. 2 and 3)
    ic1 = SimpleNamespace(competency_id=c1, name="Competency 1", target_level=3, weight=2.0)
    ic2 = SimpleNamespace(competency_id=c2, name="Competency 2", target_level=3, weight=3.0)

    # c1: level 5 -> score 100
    # c2: level 0 -> score 0
    eval1 = make_eval(competency_id=c1, demonstrated_level=5)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic1, ic2],
        evaluations=[eval1],
    )

    # Normalized weights: c1 = 2/5 = 0.4, c2 = 3/5 = 0.6
    # Overall = (100 * 0.4) + (0 * 0.6) = 40.0
    assert result.overall_score == 40.0


def test_zero_weight_handling():
    service = CompetencyScoringService()
    sid = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    ic1 = SimpleNamespace(competency_id=c1, name="C1", target_level=3, weight=0.0)
    ic2 = SimpleNamespace(competency_id=c2, name="C2", target_level=3, weight=0.0)

    eval1 = make_eval(competency_id=c1, demonstrated_level=4)  # 80
    eval2 = make_eval(competency_id=c2, demonstrated_level=2)  # 40

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic1, ic2],
        evaluations=[eval1, eval2],
    )

    # When all weights are 0, average equally: (80 + 40) / 2 = 60.0
    assert result.overall_score == 60.0


def test_missing_competency_evidence():
    """Uncovered competency receives 0 score and 0 confidence without fabricated evidence."""
    service = CompetencyScoringService()
    sid = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    ic1 = SimpleNamespace(competency_id=c1, name="Covered", target_level=3, weight=1.0)
    ic2 = SimpleNamespace(competency_id=c2, name="Uncovered", target_level=3, weight=1.0)

    eval1 = make_eval(competency_id=c1, demonstrated_level=4)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic1, ic2],
        evaluations=[eval1],
    )

    assert len(result.competency_scores) == 2
    uncovered = next(s for s in result.competency_scores if s.competency_id == c2)
    assert uncovered.demonstrated_level == 0.0
    assert uncovered.score == 0.0
    assert uncovered.evidence_count == 0
    assert uncovered.confidence == 0.0


def test_multiple_competencies_aggregation():
    service = CompetencyScoringService()
    sid = uuid4()
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    ics = [
        SimpleNamespace(competency_id=c1, name="C1", target_level=3, weight=1.0),
        SimpleNamespace(competency_id=c2, name="C2", target_level=3, weight=1.0),
        SimpleNamespace(competency_id=c3, name="C3", target_level=3, weight=1.0),
    ]
    evals = [
        make_eval(competency_id=c1, demonstrated_level=5),  # 100
        make_eval(competency_id=c2, demonstrated_level=3),  # 60
        make_eval(competency_id=c3, demonstrated_level=4),  # 80
    ]

    result = service.score_interview(session_id=sid, interview_competencies=ics, evaluations=evals)

    # Average of 100, 60, 80 with equal weights = 80.0
    assert result.overall_score == 80.0
    assert result.total_evidence_count == 3


def test_overall_score_bounds():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Edge Case", target_level=3, weight=1.0)
    eval1 = make_eval(competency_id=cid, demonstrated_level=5)

    result = service.score_interview(session_id=sid, interview_competencies=[ic], evaluations=[eval1])
    assert 0.0 <= result.overall_score <= 100.0


def test_no_fabricated_evidence():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Zero Evidence", target_level=3, weight=1.0)

    result = service.score_interview(session_id=sid, interview_competencies=[ic], evaluations=[])
    score = result.competency_scores[0]
    assert score.strengths == []
    assert score.gaps == []


def test_confidence_aggregation():
    service = CompetencyScoringService()
    sid = uuid4()
    cid = uuid4()
    ic = SimpleNamespace(competency_id=cid, name="Confidence Check", target_level=3, weight=1.0)
    eval1 = make_eval(competency_id=cid, confidence=0.70)
    eval2 = make_eval(competency_id=cid, confidence=0.90)

    result = service.score_interview(session_id=sid, interview_competencies=[ic], evaluations=[eval1, eval2])
    assert result.competency_scores[0].confidence == 0.80


def test_no_llm_calls_in_scoring():
    service = CompetencyScoringService()
    assert not hasattr(service, "provider")
    assert not hasattr(service, "client")
    assert not hasattr(service, "api_key")


# ---------------------------------------------------------------------------
# Section 10: Manual Deliverable Verification Scenario
# ---------------------------------------------------------------------------

def test_manual_verification_scenario():
    """Manual Scenario from Section 10:
    Competency A:
      target = 3
      evaluations: level 2, level 4 -> Expected average: 3 -> Expected score: 60/100
      weight = 50
    Competency B:
      target = 4
      evaluation: level 4 -> Expected: 80/100
      weight = 50
    Expected overall score: 70/100
    """
    service = CompetencyScoringService()
    sid = uuid4()
    comp_a_id = uuid4()
    comp_b_id = uuid4()

    ic_a = SimpleNamespace(
        competency_id=comp_a_id,
        name="Competency A",
        target_level=3,
        weight=50.0,
    )
    ic_b = SimpleNamespace(
        competency_id=comp_b_id,
        name="Competency B",
        target_level=4,
        weight=50.0,
    )

    eval_a1 = make_eval(competency_id=comp_a_id, demonstrated_level=2)
    eval_a2 = make_eval(competency_id=comp_a_id, demonstrated_level=4)
    eval_b = make_eval(competency_id=comp_b_id, demonstrated_level=4)

    result = service.score_interview(
        session_id=sid,
        interview_competencies=[ic_a, ic_b],
        evaluations=[eval_a1, eval_a2, eval_b],
    )

    score_a = next(s for s in result.competency_scores if s.competency_id == comp_a_id)
    score_b = next(s for s in result.competency_scores if s.competency_id == comp_b_id)

    # Competency A checks
    assert score_a.demonstrated_level == 3.0
    assert score_a.score == 60.0
    assert score_a.evidence_count == 2

    # Competency B checks
    assert score_b.demonstrated_level == 4.0
    assert score_b.score == 80.0
    assert score_b.evidence_count == 1

    # Overall score check: (60 * 0.5) + (80 * 0.5) = 70.0
    assert result.overall_score == 70.0
    assert result.total_evidence_count == 3
    assert result.completed is True
