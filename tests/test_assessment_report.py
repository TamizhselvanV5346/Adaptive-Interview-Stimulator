import io
from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from app.domain.assessment_report import AssessmentReport, CompetencyReport
from app.domain.competency_scoring import CompetencyScore, FinalAssessment
from app.reporting.assessment_report import AssessmentReportService
from app.reporting.pdf_report import PDFReportGenerator


@pytest.fixture
def sample_session_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_competency_scores() -> list[CompetencyScore]:
    return [
        CompetencyScore(
            competency_id=uuid.uuid4(),
            competency_name="System Design",
            target_level=4,
            demonstrated_level=3.5,
            score=70.0,
            weight=1.5,
            evidence_count=3,
            confidence=0.88,
            strengths=["Clear partitioning strategy", "Understands distributed caching"],
            gaps=["Did not address write-heavy replication lag"],
        ),
        CompetencyScore(
            competency_id=uuid.uuid4(),
            competency_name="Python Mastery",
            target_level=4,
            demonstrated_level=4.5,
            score=90.0,
            weight=1.0,
            evidence_count=2,
            confidence=0.92,
            strengths=["Proficient in async/await concurrency", "Proper use of metaclasses"],
            gaps=[],
        ),
    ]


@pytest.fixture
def sample_final_assessment(
    sample_session_id: uuid.UUID, sample_competency_scores: list[CompetencyScore]
) -> FinalAssessment:
    return FinalAssessment(
        session_id=sample_session_id,
        competency_scores=sample_competency_scores,
        overall_score=78.0,
        total_evidence_count=5,
        completed=True,
    )


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# 1. Valid AssessmentReport
def test_valid_assessment_report(sample_session_id: uuid.UUID, sample_competency_scores: list[CompetencyScore]):
    comp_reports = [
        CompetencyReport(
            competency_id=cs.competency_id,
            competency_name=cs.competency_name,
            score=cs.score,
            demonstrated_level=cs.demonstrated_level,
            target_level=cs.target_level,
            confidence=cs.confidence,
            evidence_count=cs.evidence_count,
            strengths=cs.strengths,
            gaps=cs.gaps,
            weight=cs.weight,
        )
        for cs in sample_competency_scores
    ]

    report = AssessmentReport(
        session_id=sample_session_id,
        overall_score=78.0,
        completed=True,
        competency_reports=comp_reports,
        total_evidence_count=5,
    )
    assert report.session_id == sample_session_id
    assert report.overall_score == 78.0
    assert report.completed is True
    assert len(report.competency_reports) == 2
    assert report.total_evidence_count == 5


# 2. Competency report validation
def test_competency_report_validation():
    cid = uuid.uuid4()
    # Blank name rejected
    with pytest.raises(ValidationError):
        CompetencyReport(
            competency_id=cid,
            competency_name="   ",
            score=80.0,
            demonstrated_level=4.0,
            target_level=4,
            confidence=0.9,
        )

    # Score > 100 rejected
    with pytest.raises(ValidationError):
        CompetencyReport(
            competency_id=cid,
            competency_name="Valid",
            score=105.0,
            demonstrated_level=4.0,
            target_level=4,
            confidence=0.9,
        )

    # Negative score rejected
    with pytest.raises(ValidationError):
        CompetencyReport(
            competency_id=cid,
            competency_name="Valid",
            score=-1.0,
            demonstrated_level=4.0,
            target_level=4,
            confidence=0.9,
        )

    # Target level out of bounds rejected
    with pytest.raises(ValidationError):
        CompetencyReport(
            competency_id=cid,
            competency_name="Valid",
            score=80.0,
            demonstrated_level=4.0,
            target_level=6,
            confidence=0.9,
        )

    # Confidence out of bounds rejected
    with pytest.raises(ValidationError):
        CompetencyReport(
            competency_id=cid,
            competency_name="Valid",
            score=80.0,
            demonstrated_level=4.0,
            target_level=4,
            confidence=1.2,
        )


# 3. Report transformation via AssessmentReportService
def test_report_transformation(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)

    assert isinstance(report, AssessmentReport)
    assert report.session_id == sample_final_assessment.session_id
    assert len(report.competency_reports) == len(sample_final_assessment.competency_scores)


# 4. Overall score preserved without recalculation
def test_overall_score_preserved(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    assert report.overall_score == sample_final_assessment.overall_score


# 5. Competency scores preserved
def test_competency_scores_preserved(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    for original, transformed in zip(sample_final_assessment.competency_scores, report.competency_reports):
        assert transformed.score == original.score
        assert transformed.competency_id == original.competency_id
        assert transformed.competency_name == original.competency_name


# 6. Demonstrated levels preserved
def test_demonstrated_levels_preserved(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    for original, transformed in zip(sample_final_assessment.competency_scores, report.competency_reports):
        assert transformed.demonstrated_level == original.demonstrated_level
        assert transformed.target_level == original.target_level


# 7. Strengths preserved
def test_strengths_preserved(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    for original, transformed in zip(sample_final_assessment.competency_scores, report.competency_reports):
        assert transformed.strengths == original.strengths


# 8. Gaps preserved
def test_gaps_preserved(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    for original, transformed in zip(sample_final_assessment.competency_scores, report.competency_reports):
        assert transformed.gaps == original.gaps


# 9. Missing evidence preserved (empty strengths/gaps handled cleanly)
def test_missing_evidence_preserved():
    session_id = uuid.uuid4()
    assessment = FinalAssessment(
        session_id=session_id,
        competency_scores=[
            CompetencyScore(
                competency_id=uuid.uuid4(),
                competency_name="Unassessed Competency",
                target_level=3,
                demonstrated_level=0.0,
                score=0.0,
                weight=1.0,
                evidence_count=0,
                confidence=0.0,
                strengths=[],
                gaps=[],
            )
        ],
        overall_score=0.0,
        total_evidence_count=0,
        completed=True,
    )
    service = AssessmentReportService()
    report = service.generate_report(assessment)
    assert report.competency_reports[0].score == 0.0
    assert report.competency_reports[0].strengths == []
    assert report.competency_reports[0].gaps == []
    assert report.competency_reports[0].evidence_count == 0


# 10. Completion status preserved
def test_completion_status_preserved():
    service = AssessmentReportService()
    assessment_in_progress = FinalAssessment(
        session_id=uuid.uuid4(),
        competency_scores=[],
        overall_score=0.0,
        total_evidence_count=0,
        completed=False,
    )
    report = service.generate_report(assessment_in_progress)
    assert report.completed is False


# 11. Deterministic report transformation
def test_deterministic_report_transformation(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    fixed_time = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
    report1 = service.generate_report(sample_final_assessment, generated_at=fixed_time)
    report2 = service.generate_report(sample_final_assessment, generated_at=fixed_time)
    assert report1 == report2


# 12. PDF generation produces bytes
def test_pdf_generation(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


# 13. PDF starts with %PDF header signature
def test_pdf_starts_with_pdf_signature(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    assert pdf_bytes.startswith(b"%PDF-")


# 14. PDF contains report title
def test_pdf_contains_report_title(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    text = extract_pdf_text(pdf_bytes)
    assert "Adaptive Interview Assessment" in text


# 15. PDF contains competency names
def test_pdf_contains_competency_names(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    text = extract_pdf_text(pdf_bytes)
    assert "System Design" in text
    assert "Python Mastery" in text


# 16. PDF handles multiple competencies
def test_pdf_handles_multiple_competencies():
    scores = [
        CompetencyScore(
            competency_id=uuid.uuid4(),
            competency_name=f"Competency {i}",
            target_level=3,
            demonstrated_level=3.0,
            score=60.0,
            weight=1.0,
            evidence_count=2,
            confidence=0.85,
            strengths=[f"Strength {i}"],
            gaps=[f"Gap {i}"],
        )
        for i in range(1, 8)
    ]
    assessment = FinalAssessment(
        session_id=uuid.uuid4(),
        competency_scores=scores,
        overall_score=60.0,
        total_evidence_count=14,
        completed=True,
    )
    service = AssessmentReportService()
    report = service.generate_report(assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    assert pdf_bytes.startswith(b"%PDF-")
    text = extract_pdf_text(pdf_bytes)
    for i in range(1, 8):
        assert f"Competency {i}" in text


# 17. PDF handles long evidence without crashing
def test_pdf_handles_long_evidence():
    long_strength = "Demonstrated deep mastery of distributed consensus algorithms including Raft and Paxos with specific implementation details regarding leader election and log replication under high network latency and intermittent partitions. " * 3
    long_gap = "Failed to articulate database partitioning strategies under dynamic horizontal auto-scaling scenarios with sharding key migration. " * 3

    scores = [
        CompetencyScore(
            competency_id=uuid.uuid4(),
            competency_name="Distributed Systems Architecture with Extremely Long Title",
            target_level=5,
            demonstrated_level=4.0,
            score=80.0,
            weight=2.0,
            evidence_count=10,
            confidence=0.95,
            strengths=[long_strength],
            gaps=[long_gap],
        )
    ]
    assessment = FinalAssessment(
        session_id=uuid.uuid4(),
        competency_scores=scores,
        overall_score=80.0,
        total_evidence_count=10,
        completed=True,
    )
    service = AssessmentReportService()
    report = service.generate_report(assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    assert pdf_bytes.startswith(b"%PDF-")
    text = extract_pdf_text(pdf_bytes)
    assert "Distributed Systems Architecture" in text
    assert "Raft and Paxos" in text


# 18. PDF does not contain hiring recommendations or decisions
def test_pdf_does_not_contain_hiring_recommendation(sample_final_assessment: FinalAssessment):
    service = AssessmentReportService()
    report = service.generate_report(sample_final_assessment)
    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    pdf_text = extract_pdf_text(pdf_bytes).lower()
    assert "hire candidate" not in pdf_text
    assert "reject candidate" not in pdf_text
    assert "hiring recommendation: pass" not in pdf_text
    assert "hiring recommendation: fail" not in pdf_text


# 19. Manual Section 7 Scenario (Comp A 60/100, Comp B 80/100 -> Overall 70/100)
def test_manual_section_7_scenario_pdf():
    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    session_id = uuid.uuid4()

    scores = [
        CompetencyScore(
            competency_id=cid_a,
            competency_name="Competency A",
            target_level=3,
            demonstrated_level=3.0,
            score=60.0,
            weight=50.0,
            evidence_count=2,
            confidence=0.85,
            strengths=["Demonstrated solid functional competence"],
            gaps=["Minor edge cases omitted"],
        ),
        CompetencyScore(
            competency_id=cid_b,
            competency_name="Competency B",
            target_level=4,
            demonstrated_level=4.0,
            score=80.0,
            weight=50.0,
            evidence_count=1,
            confidence=0.90,
            strengths=["Advanced architecture patterns applied"],
            gaps=[],
        ),
    ]

    assessment = FinalAssessment(
        session_id=session_id,
        competency_scores=scores,
        overall_score=70.0,
        total_evidence_count=3,
        completed=True,
    )

    service = AssessmentReportService()
    report = service.generate_report(assessment)
    assert report.overall_score == 70.0

    pdf_gen = PDFReportGenerator()
    pdf_bytes = pdf_gen.generate(report)

    assert pdf_bytes.startswith(b"%PDF-")
    text = extract_pdf_text(pdf_bytes)
    assert "Adaptive Interview Assessment" in text
    assert "Competency A" in text
    assert "Competency B" in text
    assert "70.0" in text or "70" in text
    assert "60.0" in text or "60" in text
    assert "80.0" in text or "80" in text
    assert "Demonstrated solid functional competence" in text
    assert "Advanced architecture patterns applied" in text
