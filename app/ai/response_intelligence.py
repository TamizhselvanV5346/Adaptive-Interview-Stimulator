from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.ai.providers.base import (
    ResponseEvaluationProvider,
    extract_competency_details,
)
from app.ai.providers.mock import MockProvider
from app.core.exceptions import ApplicationError
from app.domain.response_evaluation import ResponseEvaluation

DEFAULT_MAX_ANSWER_LENGTH = 8000


class ResponseIntelligenceService:
    """Service layer for candidate response intelligence and evaluation.

    Evaluates what the candidate's answer demonstrates against the current question and competency.
    Strictly avoids adaptive decision routing or next-question selection.
    """

    def __init__(
        self,
        provider: ResponseEvaluationProvider | None = None,
        max_answer_length: int = DEFAULT_MAX_ANSWER_LENGTH,
    ):
        self.provider: ResponseEvaluationProvider = provider or MockProvider()
        self.max_answer_length = max_answer_length

    async def evaluate_answer(
        self,
        question: Any,
        answer: str | None,
        competency: Any,
        *,
        job_context: str | None = None,
    ) -> ResponseEvaluation:
        """Evaluate a candidate's answer against a question and competency.

        Handles blank, whitespace, short, and oversized answers gracefully.
        Enforces schema validation on provider outputs.
        """
        # Graceful handling of None or non-string inputs
        if answer is None:
            raw_answer = ""
        elif isinstance(answer, str):
            raw_answer = answer
        else:
            raw_answer = str(answer)

        trimmed = raw_answer.strip()

        # Handle blank or whitespace-only answers gracefully without crashing
        if not trimmed:
            comp_id, _, _ = extract_competency_details(competency)
            return ResponseEvaluation(
                competency_id=comp_id or uuid4(),
                evidence_summary="No answer was provided by the candidate.",
                strengths=[],
                gaps=["Candidate did not provide an answer to the question."],
                relevance_score=0.0,
                depth_score=0.0,
                technical_accuracy_score=0.0,
                confidence=1.0,
                demonstrated_level=1,
                is_off_topic=True,
                off_topic_reason="Candidate submitted a blank or whitespace-only response.",
            )

        # Handle oversized answers gracefully by truncating safely without crashing
        if len(raw_answer) > self.max_answer_length:
            sanitized_answer = raw_answer[: self.max_answer_length] + " ...[truncated for evaluation]"
        else:
            sanitized_answer = raw_answer

        # Call provider (short answers are passed as-is to evaluate on merits, not penalized for brevity)
        try:
            evaluation = await self.provider.evaluate(
                question=question,
                answer=sanitized_answer,
                competency=competency,
                job_context=job_context,
            )
        except ApplicationError:
            raise
        except (ValidationError, ValueError) as val_exc:
            raise ApplicationError(
                f"Provider returned malformed evaluation: {val_exc}",
                "MALFORMED_PROVIDER_OUTPUT",
            ) from val_exc
        except Exception as exc:
            raise ApplicationError(
                f"Provider evaluation failed: {exc}",
                "PROVIDER_EVALUATION_ERROR",
            ) from exc

        # Strict validation of provider output
        if isinstance(evaluation, ResponseEvaluation):
            return evaluation

        if isinstance(evaluation, dict):
            try:
                return ResponseEvaluation.model_validate(evaluation)
            except Exception as val_exc:
                raise ApplicationError(
                    f"Provider returned malformed evaluation dictionary: {val_exc}",
                    "MALFORMED_PROVIDER_OUTPUT",
                ) from val_exc

        raise ApplicationError(
            f"Provider returned invalid response type: {type(evaluation).__name__}",
            "MALFORMED_PROVIDER_OUTPUT",
        )
