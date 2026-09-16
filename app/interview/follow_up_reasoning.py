from typing import Any

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.follow_up_reasoning import FollowUpReasoning
from app.domain.response_evaluation import ResponseEvaluation


class FollowUpReasoningService:
    """Deterministic service generating user-visible follow-up explanations from evaluation evidence."""

    def reason(
        self,
        decision: AdaptiveDecision,
        evaluation: ResponseEvaluation,
        competency: Any | None = None,
        current_difficulty: int | None = None,
    ) -> FollowUpReasoning:
        """Generate human-readable rationale ('Why This Follow-Up') for candidate/reviewer presentation.

        Parameters
        ----------
        decision : AdaptiveDecision
            The deterministic decision produced by Module 12.
        evaluation : ResponseEvaluation
            The evaluation signals produced by Module 11.
        competency : Any | None
            Current competency object or dict with name attribute.
        current_difficulty : int | None
            Current question difficulty level (1-5).

        Returns
        -------
        FollowUpReasoning
            Structured explanation model with user-visible text and explicit evidence basis.
        """
        comp_name = self._extract_name(competency)

        # -------------------------------------------------------------------
        # Action-specific templates & evidence extraction
        # -------------------------------------------------------------------
        if decision.action == AdaptiveAction.REDIRECT or getattr(evaluation, "is_off_topic", False):
            return self._build_redirect_reasoning(comp_name, evaluation)

        if decision.action == AdaptiveAction.PROBE:
            return self._build_probe_reasoning(comp_name, decision, evaluation, current_difficulty)

        if decision.action == AdaptiveAction.ESCALATE:
            return self._build_escalate_reasoning(comp_name, decision, evaluation, current_difficulty)

        if decision.action == AdaptiveAction.ADVANCE:
            return self._build_advance_reasoning(comp_name, decision, evaluation)

        # AdaptiveAction.COMPLETE
        return self._build_complete_reasoning(decision, evaluation)

    # -----------------------------------------------------------------------
    # Action template builders
    # -----------------------------------------------------------------------

    def _build_probe_reasoning(
        self,
        comp_name: str | None,
        decision: AdaptiveDecision,
        evaluation: ResponseEvaluation,
        current_difficulty: int | None,
    ) -> FollowUpReasoning:
        topic_label = comp_name or "this competency"
        gaps = [g for g in getattr(evaluation, "gaps", []) if isinstance(g, str) and g.strip()]
        demonstrated_level = int(getattr(evaluation, "demonstrated_level", 1))

        evidence_basis = [
            f"Demonstrated level: {demonstrated_level}",
            f"Action decided: {decision.action.value}",
        ]

        if gaps:
            primary_gap = gaps[0].rstrip(".")
            reason_text = (
                f"Your answer showed basic understanding, but did not provide enough evidence "
                f"about {primary_gap}. The next question probes that gap."
            )
            evidence_basis.append(f"Identified gap: {gaps[0]}")
        else:
            reason_text = (
                f"Your response did not yet provide enough evidence to establish the target "
                f"competency level for {topic_label}, so the interview will probe the same competency further."
            )
            relevance = getattr(evaluation, "relevance_score", None)
            depth = getattr(evaluation, "depth_score", None)
            if relevance is not None:
                evidence_basis.append(f"Relevance score: {relevance}/5.0")
            if depth is not None:
                evidence_basis.append(f"Depth score: {depth}/5.0")

        return FollowUpReasoning(
            action=AdaptiveAction.PROBE,
            reason=reason_text,
            evidence_basis=evidence_basis,
            competency_name=comp_name,
            difficulty_change=0,
            user_visible=True,
        )

    def _build_escalate_reasoning(
        self,
        comp_name: str | None,
        decision: AdaptiveDecision,
        evaluation: ResponseEvaluation,
        current_difficulty: int | None,
    ) -> FollowUpReasoning:
        topic_label = comp_name or "the current competency"
        target_diff = decision.target_difficulty or 3
        curr_diff = current_difficulty or max(1, target_diff - 1)
        diff_change = target_diff - curr_diff
        demonstrated_level = int(getattr(evaluation, "demonstrated_level", 3))

        reason_text = (
            f"You demonstrated the target competency level for {topic_label} at difficulty {curr_diff}, "
            f"so the interview is increasing the challenge to difficulty {target_diff} to test the skill "
            "under a more demanding scenario."
        )

        evidence_basis = [
            f"Demonstrated level: {demonstrated_level}",
            f"Previous difficulty: {curr_diff}",
            f"Next difficulty: {target_diff}",
        ]

        strengths = [s for s in getattr(evaluation, "strengths", []) if isinstance(s, str) and s.strip()]
        if strengths:
            evidence_basis.append(f"Demonstrated strength: {strengths[0]}")

        return FollowUpReasoning(
            action=AdaptiveAction.ESCALATE,
            reason=reason_text,
            evidence_basis=evidence_basis,
            competency_name=comp_name,
            difficulty_change=diff_change,
            user_visible=True,
        )

    def _build_advance_reasoning(
        self,
        comp_name: str | None,
        decision: AdaptiveDecision,
        evaluation: ResponseEvaluation,
    ) -> FollowUpReasoning:
        topic_label = comp_name or "the current competency"
        demonstrated_level = int(getattr(evaluation, "demonstrated_level", 3))

        reason_text = (
            f"You demonstrated sufficient evidence for {topic_label}, "
            "so the interview is moving to another configured competency."
        )

        evidence_basis = [
            f"Competency satisfied: {topic_label}",
            f"Demonstrated level: {demonstrated_level}",
        ]

        return FollowUpReasoning(
            action=AdaptiveAction.ADVANCE,
            reason=reason_text,
            evidence_basis=evidence_basis,
            competency_name=comp_name,
            difficulty_change=None,
            user_visible=True,
        )

    def _build_redirect_reasoning(
        self,
        comp_name: str | None,
        evaluation: ResponseEvaluation,
    ) -> FollowUpReasoning:
        off_topic_reason = getattr(evaluation, "off_topic_reason", None)

        if off_topic_reason and off_topic_reason.strip():
            cleaned_reason = off_topic_reason.strip().rstrip(".")
            reason_text = (
                f"Your response appeared off-topic and did not address the current question ({cleaned_reason}), "
                "so the interview will redirect you back to the topic before continuing the assessment."
            )
            evidence_basis = [
                "Response marked off-topic",
                f"Off-topic detail: {off_topic_reason}",
            ]
        else:
            reason_text = (
                "Your response appeared off-topic and did not address the current question, "
                "so the interview will redirect you back to the topic before continuing the assessment."
            )
            evidence_basis = [
                "Response marked off-topic",
            ]

        return FollowUpReasoning(
            action=AdaptiveAction.REDIRECT,
            reason=reason_text,
            evidence_basis=evidence_basis,
            competency_name=comp_name,
            difficulty_change=0,
            user_visible=True,
        )

    def _build_complete_reasoning(
        self,
        decision: AdaptiveDecision,
        evaluation: ResponseEvaluation,
    ) -> FollowUpReasoning:
        reason_text = (
            "The required interview evidence has been collected or the interview turn limit has been reached, "
            "so the assessment is complete."
        )

        evidence_basis = [
            f"Turn number: {decision.based_on_turn}",
            "Completion criteria satisfied",
        ]

        return FollowUpReasoning(
            action=AdaptiveAction.COMPLETE,
            reason=reason_text,
            evidence_basis=evidence_basis,
            competency_name=None,
            difficulty_change=None,
            user_visible=True,
        )

    def _extract_name(self, competency: Any | None) -> str | None:
        if competency is None:
            return None
        name = getattr(competency, "name", None)
        if name is None and isinstance(competency, dict):
            name = competency.get("name")
        return name if isinstance(name, str) and name.strip() else None
