from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.response_evaluation import ResponseEvaluation


class ResponseEvaluationProvider(ABC):
    """Abstract interface for candidate answer evaluation providers."""

    @abstractmethod
    async def evaluate(
        self,
        question: Any,
        answer: str,
        competency: Any,
        *,
        job_context: str | None = None,
    ) -> ResponseEvaluation:
        """Evaluate a candidate's answer against the given question and competency.

        Parameters
        ----------
        question : Any
            The Question model, dict, or object containing question details
            (question_text, expected_signal, etc.).
        answer : str
            The candidate's response text.
        competency : Any
            The Competency model, dict, or object containing competency details
            (id, name, description).
        job_context : str | None
            Optional additional context regarding the role or interview.

        Returns
        -------
        ResponseEvaluation
            Validated evaluation result.
        """
        pass


def extract_competency_details(competency: Any) -> tuple[UUID | None, str, str]:
    """Extract (competency_id, name, description) from various competency representations."""
    competency_id = getattr(competency, "id", None)
    name = getattr(competency, "name", None)
    description = getattr(competency, "description", None)

    if isinstance(competency, dict):
        competency_id = competency.get("id", competency_id)
        name = competency.get("name", name)
        description = competency.get("description", description)
    elif isinstance(competency, str):
        name = name or competency
        description = description or competency

    if isinstance(competency_id, str):
        try:
            competency_id = UUID(competency_id)
        except ValueError:
            pass

    return competency_id, name or "General Competency", description or "Evaluation competency"


def extract_question_details(question: Any) -> tuple[UUID | None, str, str]:
    """Extract (question_id, question_text, expected_signal) from various representations."""
    question_id = getattr(question, "id", None)
    question_text = getattr(question, "question_text", None)
    expected_signal = getattr(question, "expected_signal", None)

    if isinstance(question, dict):
        question_id = question.get("id", question_id)
        question_text = question.get("question_text", question.get("text", question_text))
        expected_signal = question.get("expected_signal", expected_signal)
    elif isinstance(question, str):
        question_text = question_text or question
        expected_signal = expected_signal or "Clear, direct, evidence-based answer."

    if isinstance(question_id, str):
        try:
            question_id = UUID(question_id)
        except ValueError:
            pass

    return question_id, question_text or "Interview question", expected_signal or "Expected signal"
