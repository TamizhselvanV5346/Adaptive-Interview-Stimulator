from collections import deque
from typing import Any
from uuid import UUID, uuid4

from app.ai.providers.base import (
    ResponseEvaluationProvider,
    extract_competency_details,
    extract_question_details,
)
from app.domain.response_evaluation import ResponseEvaluation

DEFAULT_MOCK_COMPETENCY_ID = UUID("00000000-0000-0000-0000-000000000001")


class MockProvider(ResponseEvaluationProvider):
    """Deterministic mock provider for offline tests without calling external APIs."""

    def __init__(
        self,
        *,
        force_off_topic: bool = False,
        default_evaluation: ResponseEvaluation | None = None,
    ):
        self.force_off_topic = force_off_topic
        self.default_evaluation = default_evaluation
        self._queued_evaluations: deque[Any] = deque()
        self.call_count = 0
        self.last_call: dict[str, Any] | None = None

    def queue_evaluation(self, evaluation: ResponseEvaluation | dict[str, Any] | Any) -> None:
        """Queue a specific evaluation or raw object to be returned on subsequent evaluate calls."""
        self._queued_evaluations.append(evaluation)

    def clear_queue(self) -> None:
        """Clear all queued evaluations."""
        self._queued_evaluations.clear()

    async def evaluate(
        self,
        question: Any,
        answer: str,
        competency: Any,
        *,
        job_context: str | None = None,
    ) -> ResponseEvaluation:
        self.call_count += 1
        self.last_call = {
            "question": question,
            "answer": answer,
            "competency": competency,
            "job_context": job_context,
        }

        # If a response has been explicitly queued, return it (allowing testing of validation and malformed outputs)
        if self._queued_evaluations:
            return self._queued_evaluations.popleft()  # type: ignore[return-value]

        if self.default_evaluation is not None:
            return self.default_evaluation

        competency_id, comp_name, _ = extract_competency_details(competency)
        effective_comp_id = competency_id or DEFAULT_MOCK_COMPETENCY_ID

        _, question_text, _ = extract_question_details(question)
        answer_clean = answer.strip() if answer else ""

        # Blank or whitespace-only answer
        if not answer_clean:
            return ResponseEvaluation(
                competency_id=effective_comp_id,
                evidence_summary="No answer provided by the candidate.",
                strengths=[],
                gaps=["Candidate did not provide a response to the question."],
                relevance_score=0.0,
                depth_score=0.0,
                technical_accuracy_score=0.0,
                confidence=1.0,
                demonstrated_level=1,
                is_off_topic=True,
                off_topic_reason="Candidate submitted a blank or empty response.",
            )

        # Off-topic detection
        is_off_topic = self.force_off_topic
        off_topic_reason: str | None = None

        lower_answer = answer_clean.lower()
        lower_question = question_text.lower()

        # Specific example from spec:
        # Question: "Describe a production incident you personally debugged."
        # Answer: "My favorite programming language is Python."
        if "favorite programming language" in lower_answer or "[off_topic]" in lower_answer:
            is_off_topic = True
            off_topic_reason = "Candidate answered with language preferences rather than addressing the question topic."
        elif "production incident" in lower_question and "python" in lower_answer and "incident" not in lower_answer and "debug" not in lower_answer:
            is_off_topic = True
            off_topic_reason = "Candidate answered with language preferences rather than describing a production incident."

        if is_off_topic:
            return ResponseEvaluation(
                competency_id=effective_comp_id,
                evidence_summary="Candidate's response was off-topic and did not demonstrate the target competency.",
                strengths=["Communicated in complete grammatical sentences"],
                gaps=["Did not address the question asked", "No relevant technical evidence demonstrated"],
                relevance_score=0.5,
                depth_score=1.0,
                technical_accuracy_score=1.0,
                confidence=0.95,
                demonstrated_level=1,
                is_off_topic=True,
                off_topic_reason=off_topic_reason or "Response did not address the topic of the question.",
            )

        # Valid on-topic evaluation
        return ResponseEvaluation(
            competency_id=effective_comp_id,
            evidence_summary=f"Candidate demonstrated relevant practical knowledge of {comp_name}.",
            strengths=[
                "Clear explanation of methodology and root cause analysis",
                "Demonstrated systematic technical problem-solving",
            ],
            gaps=[
                "Could provide further details on long-term automated prevention",
            ],
            relevance_score=4.0,
            depth_score=3.5,
            technical_accuracy_score=4.0,
            confidence=0.9,
            demonstrated_level=3,
            is_off_topic=False,
            off_topic_reason=None,
        )
