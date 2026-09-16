from datetime import datetime, timezone
from uuid import UUID
from app.domain.assessment_report import AssessmentReport, CompetencyReport
from app.domain.competency_scoring import FinalAssessment, CompetencyScore


class AssessmentReportService:
    """
    Transforms deterministic FinalAssessment instances from Module 19
    into presentation-ready AssessmentReport structures.
    Does NOT recalculate or modify scores.
    """

    def generate_report(
        self,
        assessment: FinalAssessment,
        candidate_id: UUID | None = None,
        session_title: str | None = None,
        generated_at: datetime | None = None,
    ) -> AssessmentReport:
        competency_reports: list[CompetencyReport] = []
        for cs in assessment.competency_scores:
            competency_reports.append(
                CompetencyReport(
                    competency_id=cs.competency_id,
                    competency_name=cs.competency_name,
                    score=cs.score,
                    demonstrated_level=cs.demonstrated_level,
                    target_level=cs.target_level,
                    confidence=cs.confidence,
                    evidence_count=cs.evidence_count,
                    strengths=list(cs.strengths),
                    gaps=list(cs.gaps),
                    weight=cs.weight,
                )
            )

        return AssessmentReport(
            session_id=assessment.session_id,
            generated_at=generated_at or datetime.now(timezone.utc),
            overall_score=assessment.overall_score,
            completed=assessment.completed,
            competency_reports=competency_reports,
            total_evidence_count=assessment.total_evidence_count,
            candidate_id=candidate_id,
            session_title=session_title,
        )
