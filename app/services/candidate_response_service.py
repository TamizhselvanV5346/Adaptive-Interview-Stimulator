from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.candidate_response import CandidateResponse
from app.database.models.interview_session import InterviewSession
from app.database.models.question import Question
from app.domain.response_evaluation import ResponseEvaluation


class CandidateResponseService:
    """Service layer for persisting and retrieving candidate interview responses."""

    @staticmethod
    async def record_response(
        db: AsyncSession,
        organization_id: UUID,
        interview_session_id: UUID,
        question_id: UUID,
        turn_number: int,
        candidate_answer: str,
        evaluation: ResponseEvaluation | dict[str, Any] | None = None,
    ) -> CandidateResponse:
        """Persist a candidate response with strict organization isolation.

        Parameters
        ----------
        db : AsyncSession
            Database session.
        organization_id : UUID
            Tenant organization identifier.
        interview_session_id : UUID
            Active interview session identifier.
        question_id : UUID
            Question answered in this turn.
        turn_number : int
            Turn number (must be non-negative).
        candidate_answer : str
            Candidate answer text.
        evaluation : ResponseEvaluation | dict | None
            Optional structured evaluation to persist with response.

        Returns
        -------
        CandidateResponse
            Persisted response record.
        """
        if turn_number < 0:
            raise ApplicationError(
                "Turn number cannot be negative",
                "INVALID_TURN_NUMBER",
            )

        # Enforce tenant isolation for interview session
        session = await db.scalar(
            select(InterviewSession).where(
                InterviewSession.id == interview_session_id,
                InterviewSession.organization_id == organization_id,
            )
        )
        if session is None:
            raise ApplicationError(
                "Interview session was not found in this organization",
                "INTERVIEW_SESSION_NOT_FOUND",
            )

        # Enforce tenant isolation for question
        question = await db.scalar(
            select(Question).where(
                Question.id == question_id,
                Question.organization_id == organization_id,
            )
        )
        if question is None:
            raise ApplicationError(
                "Question was not found in this organization",
                "QUESTION_NOT_FOUND",
            )

        # Serialize evaluation
        eval_dict: dict[str, Any] | None = None
        if isinstance(evaluation, ResponseEvaluation):
            eval_dict = evaluation.model_dump(mode="json")
        elif isinstance(evaluation, dict):
            # Validate through model before storing to ensure validity
            eval_dict = ResponseEvaluation.model_validate(evaluation).model_dump(mode="json")

        response = CandidateResponse(
            organization_id=organization_id,
            interview_session_id=interview_session_id,
            question_id=question_id,
            turn_number=turn_number,
            candidate_answer=candidate_answer,
            evaluation_result=eval_dict,
        )

        db.add(response)
        await db.commit()
        await db.refresh(response)

        return response

    @staticmethod
    async def get_response(
        db: AsyncSession,
        organization_id: UUID,
        response_id: UUID,
    ) -> CandidateResponse:
        """Retrieve a candidate response by ID with strict tenant isolation."""
        response = await db.scalar(
            select(CandidateResponse).where(
                CandidateResponse.id == response_id,
                CandidateResponse.organization_id == organization_id,
            )
        )
        if response is None:
            raise ApplicationError(
                "Candidate response was not found in this organization",
                "CANDIDATE_RESPONSE_NOT_FOUND",
            )
        return response

    @staticmethod
    async def get_session_responses(
        db: AsyncSession,
        organization_id: UUID,
        interview_session_id: UUID,
    ) -> list[CandidateResponse]:
        """Retrieve all candidate responses for a session ordered by turn number."""
        # Verify session belongs to org
        session = await db.scalar(
            select(InterviewSession).where(
                InterviewSession.id == interview_session_id,
                InterviewSession.organization_id == organization_id,
            )
        )
        if session is None:
            raise ApplicationError(
                "Interview session was not found in this organization",
                "INTERVIEW_SESSION_NOT_FOUND",
            )

        query = (
            select(CandidateResponse)
            .where(
                CandidateResponse.interview_session_id == interview_session_id,
                CandidateResponse.organization_id == organization_id,
            )
            .order_by(CandidateResponse.turn_number.asc())
        )
        result = await db.scalars(query)
        return list(result.all())
