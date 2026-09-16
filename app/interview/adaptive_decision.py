from typing import Any
from uuid import UUID

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.response_evaluation import ResponseEvaluation


class AdaptiveDecisionEngine:
    """Deterministic decision engine determining next interview actions based on candidate response evidence."""

    def decide(
        self,
        *,
        evaluation: ResponseEvaluation,
        competency: Any,
        interview_competencies: list[Any],
        current_question: Any,
        current_turn: int,
        min_turns: int,
        max_turns: int,
        remaining_eligible_questions: bool = True,
    ) -> AdaptiveDecision:
        """Determine the next adaptive action deterministically.

        Parameters
        ----------
        evaluation : ResponseEvaluation
            Evaluation produced by Module 11.
        competency : Any
            The current competency (Competency model or object with id/name).
        interview_competencies : list[Any]
            List of configured InterviewCompetency entries for this interview definition.
        current_question : Any
            The current question (Question model or object with id/difficulty_level).
        current_turn : int
            Current turn number (1-indexed).
        min_turns : int
            Configured minimum interview turns.
        max_turns : int
            Configured maximum interview turns.
        remaining_eligible_questions : bool
            Whether eligible questions remain in the pool.

        Returns
        -------
        AdaptiveDecision
            Strongly typed deterministic decision.
        """
        curr_comp_id = self._extract_id(competency)
        comp_name = getattr(competency, "name", "Current Competency")
        current_difficulty = self._extract_difficulty(current_question)
        confidence_val = round(max(0.0, min(1.0, float(getattr(evaluation, "confidence", 0.9)))), 2)

        # -------------------------------------------------------------------
        # Priority 1: Hard Max Turn Limit
        # -------------------------------------------------------------------
        if current_turn >= max_turns:
            return AdaptiveDecision(
                action=AdaptiveAction.COMPLETE,
                reason=(
                    f"Maximum interview turns reached ({current_turn}/{max_turns}). "
                    "Concluding interview session."
                ),
                target_competency_id=None,
                target_difficulty=None,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # -------------------------------------------------------------------
        # Priority 2: Question Pool Exhaustion
        # -------------------------------------------------------------------
        if not remaining_eligible_questions:
            return AdaptiveDecision(
                action=AdaptiveAction.COMPLETE,
                reason=(
                    "No further eligible questions remain in the pool for this interview definition. "
                    "Concluding interview session."
                ),
                target_competency_id=None,
                target_difficulty=None,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # -------------------------------------------------------------------
        # Priority 3: Off-Topic Answer Detection
        # -------------------------------------------------------------------
        if getattr(evaluation, "is_off_topic", False):
            off_topic_reason = getattr(evaluation, "off_topic_reason", None) or "Answer did not address the question."
            return AdaptiveDecision(
                action=AdaptiveAction.REDIRECT,
                reason=(
                    f"Candidate response was off-topic: {off_topic_reason} "
                    "A conversational redirect is required before continuing assessment."
                ),
                target_competency_id=curr_comp_id,
                target_difficulty=current_difficulty,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # Retrieve target level for current competency
        target_level = self._get_target_level(curr_comp_id, interview_competencies)

        # Retrieve candidate demonstrated level and scores
        demonstrated_level = int(getattr(evaluation, "demonstrated_level", 1))
        relevance_score = float(getattr(evaluation, "relevance_score", 3.0))
        depth_score = float(getattr(evaluation, "depth_score", 3.0))

        is_insufficient = (
            demonstrated_level < target_level
            or relevance_score < 3.0
            or depth_score < 2.5
        )

        # -------------------------------------------------------------------
        # Priority 4: Weak / Insufficient Evidence (PROBE)
        # -------------------------------------------------------------------
        if is_insufficient:
            probe_difficulty = max(1, min(5, current_difficulty))
            return AdaptiveDecision(
                action=AdaptiveAction.PROBE,
                reason=(
                    f"Candidate demonstrated level {demonstrated_level}, which has not yet satisfied "
                    f"the target level {target_level} for {comp_name}. "
                    f"Probing the same competency at difficulty {probe_difficulty} for deeper evidence."
                ),
                target_competency_id=curr_comp_id,
                target_difficulty=probe_difficulty,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # -------------------------------------------------------------------
        # Priority 5: Strong Evidence & Difficulty Escalation (ESCALATE)
        # -------------------------------------------------------------------
        if demonstrated_level >= target_level and current_difficulty < 5:
            next_difficulty = min(5, current_difficulty + 1)
            return AdaptiveDecision(
                action=AdaptiveAction.ESCALATE,
                reason=(
                    f"Candidate demonstrated level {demonstrated_level} (meeting/exceeding target level {target_level}) "
                    f"for {comp_name}. Increasing difficulty from {current_difficulty} to {next_difficulty} "
                    "to test deeper technical mastery under higher complexity."
                ),
                target_competency_id=curr_comp_id,
                target_difficulty=next_difficulty,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # -------------------------------------------------------------------
        # Priority 6: Competency Satisfied (ADVANCE or COMPLETE)
        # -------------------------------------------------------------------
        # Current competency has met/exceeded target level and is at max difficulty or satisfied
        other_competencies = self._get_other_competencies(curr_comp_id, interview_competencies)

        if other_competencies:
            next_ic = other_competencies[0]
            next_comp_id = self._extract_competency_id(next_ic)
            next_target_level = int(getattr(next_ic, "target_level", 3))
            next_diff = max(1, min(5, next_target_level))
            return AdaptiveDecision(
                action=AdaptiveAction.ADVANCE,
                reason=(
                    f"Competency '{comp_name}' is sufficiently demonstrated. "
                    f"Advancing to next configured competency to evaluate remaining interview requirements."
                ),
                target_competency_id=next_comp_id,
                target_difficulty=next_diff,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # All configured competencies are satisfied
        if current_turn >= min_turns:
            return AdaptiveDecision(
                action=AdaptiveAction.COMPLETE,
                reason=(
                    f"Minimum turn requirement satisfied ({current_turn} >= {min_turns}) "
                    "and all configured competencies have been evaluated. Concluding interview session."
                ),
                target_competency_id=None,
                target_difficulty=None,
                confidence=confidence_val,
                based_on_turn=current_turn,
            )

        # Minimum turns not reached and no other competencies configured: safe continuation
        probe_diff = max(1, min(5, target_level))
        return AdaptiveDecision(
            action=AdaptiveAction.PROBE,
            reason=(
                f"Candidate met target level for {comp_name}, but minimum interview turns "
                f"({min_turns}) have not been reached ({current_turn} turns completed). "
                f"Continuing evaluation on {comp_name} at difficulty {probe_diff} to ensure thorough coverage."
            ),
            target_competency_id=curr_comp_id,
            target_difficulty=probe_diff,
            confidence=confidence_val,
            based_on_turn=current_turn,
        )

    # -----------------------------------------------------------------------
    # Helper extraction and sorting methods
    # -----------------------------------------------------------------------

    def _extract_id(self, obj: Any) -> UUID | None:
        if obj is None:
            return None
        raw_id = getattr(obj, "id", None)
        if raw_id is None and isinstance(obj, dict):
            raw_id = obj.get("id")
        if isinstance(raw_id, str):
            try:
                return UUID(raw_id)
            except ValueError:
                return None
        return raw_id if isinstance(raw_id, UUID) else None

    def _extract_competency_id(self, item: Any) -> UUID | None:
        comp_id = getattr(item, "competency_id", None)
        if comp_id is None and isinstance(item, dict):
            comp_id = item.get("competency_id") or item.get("id")
        if isinstance(comp_id, str):
            try:
                return UUID(comp_id)
            except ValueError:
                return None
        return comp_id if isinstance(comp_id, UUID) else None

    def _extract_difficulty(self, question: Any) -> int:
        diff = getattr(question, "difficulty_level", None)
        if diff is None and isinstance(question, dict):
            diff = question.get("difficulty_level")
        try:
            return int(diff) if diff is not None else 1
        except (ValueError, TypeError):
            return 1

    def _get_target_level(self, comp_id: UUID | None, interview_competencies: list[Any]) -> int:
        if not comp_id or not interview_competencies:
            return 3
        for item in interview_competencies:
            item_comp_id = self._extract_competency_id(item)
            if item_comp_id == comp_id:
                target_level = getattr(item, "target_level", None)
                if target_level is None and isinstance(item, dict):
                    target_level = item.get("target_level")
                try:
                    return int(target_level) if target_level is not None else 3
                except (ValueError, TypeError):
                    return 3
        return 3

    def _get_other_competencies(
        self,
        current_comp_id: UUID | None,
        interview_competencies: list[Any],
    ) -> list[Any]:
        others = []
        for item in interview_competencies:
            item_comp_id = self._extract_competency_id(item)
            if item_comp_id and item_comp_id != current_comp_id:
                others.append(item)

        # Sort other competencies by weight descending, display_order ascending
        def sort_key(item: Any) -> tuple[float, int]:
            weight = getattr(item, "weight", None)
            if weight is None and isinstance(item, dict):
                weight = item.get("weight", 1.0)
            try:
                w_val = float(weight) if weight is not None else 1.0
            except (ValueError, TypeError):
                w_val = 1.0

            disp = getattr(item, "display_order", None)
            if disp is None and isinstance(item, dict):
                disp = item.get("display_order", 1)
            try:
                d_val = int(disp) if disp is not None else 1
            except (ValueError, TypeError):
                d_val = 1

            return (-w_val, d_val)

        others.sort(key=sort_key)
        return others
