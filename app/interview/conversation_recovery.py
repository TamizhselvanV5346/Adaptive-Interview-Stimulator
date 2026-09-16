from typing import Any

from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.conversation_recovery import ConversationRecovery
from app.domain.response_evaluation import ResponseEvaluation


class ConversationRecoveryService:
    """Deterministic service providing conversational recovery when candidates go off-topic."""

    def __init__(self, default_max_retries: int = 2):
        self.default_max_retries = default_max_retries

    def recover(
        self,
        *,
        question: Any,
        evaluation: ResponseEvaluation,
        decision: AdaptiveDecision,
        retry_count: int = 0,
        max_retries: int | None = None,
    ) -> ConversationRecovery:
        """Construct a graceful, neutral redirect response preserving the original question.

        Parameters
        ----------
        question : Any
            The current question object, dict, or text.
        evaluation : ResponseEvaluation
            Evaluation produced by Module 11 indicating off-topic status.
        decision : AdaptiveDecision
            Decision produced by Module 12.
        retry_count : int
            Current retry counter for this question/topic (0-indexed).
        max_retries : int | None
            Maximum allowed redirects before transitioning forward.

        Returns
        -------
        ConversationRecovery
            Domain model containing redirect message, preserved question, and retry metadata.
        """
        limit = max_retries if max_retries is not None else self.default_max_retries
        q_text = self._extract_question_text(question)
        off_topic_reason = getattr(evaluation, "off_topic_reason", None)
        is_exceeded = retry_count >= limit

        if is_exceeded:
            redirect_msg = (
                "We have reached the redirect limit for this question. "
                "Let's move forward to the next part of the interview."
            )
            should_re_evaluate = False
        elif retry_count == 0:
            # First attempt: Graceful, supportive redirect
            redirect_msg = (
                f"Let's stay with the current question. You were asked: \"{q_text}\". "
                "Could you describe the steps and approach you would take?"
            )
            should_re_evaluate = True
        else:
            # Subsequent attempt before limit: Clearer, more direct redirect
            redirect_msg = (
                f"Before moving on, we'd like to hear your specific thoughts on the original question: "
                f"\"{q_text}\". Please focus directly on answering this prompt."
            )
            should_re_evaluate = True

        return ConversationRecovery(
            action=decision.action if isinstance(decision.action, AdaptiveAction) else AdaptiveAction.REDIRECT,
            redirect_message=redirect_msg,
            original_question=question,
            original_question_text=q_text,
            off_topic_reason=off_topic_reason,
            retry_count=retry_count,
            max_retries=limit,
            should_re_evaluate=should_re_evaluate,
            is_max_retries_exceeded=is_exceeded,
        )

    def _extract_question_text(self, question: Any) -> str:
        if question is None:
            return "the current question"
        if isinstance(question, str):
            clean = question.strip()
            return clean if clean else "the current question"
        raw = getattr(question, "question_text", None)
        if raw is None and isinstance(question, dict):
            raw = question.get("question_text")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return "the current question"
