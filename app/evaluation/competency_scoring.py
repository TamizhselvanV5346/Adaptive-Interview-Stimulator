from typing import Any
from uuid import UUID

from app.domain.competency_scoring import CompetencyScore, FinalAssessment
from app.domain.response_evaluation import ResponseEvaluation


class CompetencyScoringService:
    """Deterministic scoring engine aggregating interview evidence into competency scores."""

    def score_interview(
        self,
        *,
        session_id: UUID,
        interview_competencies: list[Any],
        evaluations: list[Any],
        competency_names: dict[UUID, str] | None = None,
        completed: bool = True,
    ) -> FinalAssessment:
        """Aggregate turn-by-turn evaluations into a final scored assessment report.

        Parameters
        ----------
        session_id : UUID
            The interview session identifier.
        interview_competencies : list[Any]
            The configured competencies for this interview definition.
        evaluations : list[Any]
            List of response evaluations (ResponseEvaluation objects, CandidateResponse models, or dicts).
        competency_names : dict[UUID, str] | None
            Optional mapping of competency_id to human-readable names.
        completed : bool
            Whether the interview session has completed.

        Returns
        -------
        FinalAssessment
            Authoritative assessment containing per-competency scores and weighted overall score.
        """
        names_map = competency_names or {}
        competency_scores: list[CompetencyScore] = []
        total_evidence_count = 0

        # Extract structured evaluation items
        extracted_evals = self._extract_evaluations(evaluations)

        for ic in interview_competencies:
            comp_id = self._extract_uuid(ic)
            if not comp_id:
                continue

            comp_name = self._resolve_name(ic, comp_id, names_map)
            target_lvl = self._extract_int(ic, "target_level", 3)
            raw_weight = self._extract_float(ic, "weight", 1.0)
            weight = max(0.0, raw_weight)

            # Find matching evaluations for this competency
            matched = [ev for ev in extracted_evals if ev["competency_id"] == comp_id]
            count = len(matched)
            total_evidence_count += count

            if count > 0:
                mean_level = round(sum(ev["demonstrated_level"] for ev in matched) / count, 2)
                # Map 1-5 level linearly to 0-100 score
                score = round((mean_level / 5.0) * 100.0, 2)
                confidence = round(sum(ev["confidence"] for ev in matched) / count, 2)

                # Deduplicate strengths and gaps preserving discovery order
                strengths: list[str] = []
                for ev in matched:
                    for s in ev.get("strengths", []):
                        if s and s not in strengths:
                            strengths.append(s)

                gaps: list[str] = []
                for ev in matched:
                    for g in ev.get("gaps", []):
                        if g and g not in gaps:
                            gaps.append(g)
            else:
                mean_level = 0.0
                score = 0.0
                confidence = 0.0
                strengths = []
                gaps = []

            competency_scores.append(
                CompetencyScore(
                    competency_id=comp_id,
                    competency_name=comp_name,
                    target_level=target_lvl,
                    demonstrated_level=mean_level,
                    score=score,
                    weight=weight,
                    evidence_count=count,
                    strengths=strengths,
                    gaps=gaps,
                    confidence=confidence,
                )
            )

        # Compute weighted overall score
        overall_score = self._compute_overall_score(competency_scores)

        return FinalAssessment(
            session_id=session_id,
            competency_scores=competency_scores,
            overall_score=overall_score,
            total_evidence_count=total_evidence_count,
            completed=completed,
        )

    def _compute_overall_score(self, scores: list[CompetencyScore]) -> float:
        """Compute the weighted overall assessment score with safe weight normalization."""
        if not scores:
            return 0.0

        total_weight = sum(s.weight for s in scores)
        if total_weight > 0:
            weighted_sum = sum(s.score * (s.weight / total_weight) for s in scores)
            return round(min(100.0, max(0.0, weighted_sum)), 2)

        # If all weights are 0, weight competencies equally
        avg_score = sum(s.score for s in scores) / len(scores)
        return round(min(100.0, max(0.0, avg_score)), 2)

    def _extract_evaluations(self, evaluations: list[Any]) -> list[dict[str, Any]]:
        """Normalize various evaluation representations into standard dicts."""
        normalized: list[dict[str, Any]] = []

        for item in evaluations:
            if item is None:
                continue

            if isinstance(item, ResponseEvaluation):
                normalized.append({
                    "competency_id": item.competency_id,
                    "demonstrated_level": float(item.demonstrated_level),
                    "confidence": float(item.confidence),
                    "strengths": list(item.strengths),
                    "gaps": list(item.gaps),
                })
                continue

            # Check if CandidateResponse database model with evaluation_result
            eval_result = getattr(item, "evaluation_result", None)
            if eval_result and isinstance(eval_result, dict):
                comp_id = eval_result.get("competency_id")
                if isinstance(comp_id, str):
                    try:
                        comp_id = UUID(comp_id)
                    except ValueError:
                        comp_id = None
                normalized.append({
                    "competency_id": comp_id or getattr(item, "competency_id", None),
                    "demonstrated_level": float(eval_result.get("demonstrated_level", 1)),
                    "confidence": float(eval_result.get("confidence", 0.0)),
                    "strengths": list(eval_result.get("strengths", [])),
                    "gaps": list(eval_result.get("gaps", [])),
                })
                continue

            # Dict representation
            if isinstance(item, dict):
                comp_id = item.get("competency_id")
                if isinstance(comp_id, str):
                    try:
                        comp_id = UUID(comp_id)
                    except ValueError:
                        comp_id = None
                normalized.append({
                    "competency_id": comp_id,
                    "demonstrated_level": float(item.get("demonstrated_level", 1)),
                    "confidence": float(item.get("confidence", 0.0)),
                    "strengths": list(item.get("strengths", [])),
                    "gaps": list(item.get("gaps", [])),
                })
                continue

            # Generic object with attributes
            comp_id = getattr(item, "competency_id", None)
            if comp_id:
                normalized.append({
                    "competency_id": comp_id,
                    "demonstrated_level": float(getattr(item, "demonstrated_level", 1)),
                    "confidence": float(getattr(item, "confidence", 0.0)),
                    "strengths": list(getattr(item, "strengths", [])),
                    "gaps": list(getattr(item, "gaps", [])),
                })

        return normalized

    def _extract_uuid(self, obj: Any) -> UUID | None:
        raw = getattr(obj, "competency_id", None)
        if raw is None:
            raw = getattr(obj, "id", None)
        if raw is None and isinstance(obj, dict):
            raw = obj.get("competency_id") or obj.get("id")
        if isinstance(raw, str):
            try:
                return UUID(raw)
            except ValueError:
                return None
        return raw if isinstance(raw, UUID) else None

    def _resolve_name(self, obj: Any, comp_id: UUID, names_map: dict[UUID, str]) -> str:
        if comp_id in names_map:
            return names_map[comp_id]
        comp_obj = getattr(obj, "competency", None)
        if comp_obj:
            c_name = getattr(comp_obj, "name", None)
            if isinstance(c_name, str) and c_name.strip():
                return c_name.strip()
        obj_name = getattr(obj, "name", None)
        if isinstance(obj_name, str) and obj_name.strip():
            return obj_name.strip()
        if isinstance(obj, dict):
            dict_name = obj.get("name") or obj.get("competency_name")
            if isinstance(dict_name, str) and dict_name.strip():
                return dict_name.strip()
        return f"Competency {str(comp_id)[:8]}"

    def _extract_int(self, obj: Any, attr: str, default: int) -> int:
        val = getattr(obj, attr, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(attr)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _extract_float(self, obj: Any, attr: str, default: float) -> float:
        val = getattr(obj, attr, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(attr)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default
