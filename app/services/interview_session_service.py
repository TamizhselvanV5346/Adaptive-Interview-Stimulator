from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.candidate import Candidate
from app.database.models.interview_definition import InterviewDefinition
from app.database.models.interview_session import (
    InterviewSession,
    InterviewSessionStatus,
)


class InterviewSessionService:
    """Application service for interview session lifecycle operations."""

    @staticmethod
    async def create_session(
        db: AsyncSession,
        organization_id: UUID,
        interview_definition_id: UUID,
        candidate_id: UUID,
    ) -> InterviewSession:
        candidate = await db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.organization_id == organization_id,
            )
        )
        if candidate is None:
            raise ApplicationError(
                "Candidate was not found in this organization",
                "CANDIDATE_NOT_FOUND",
            )

        interview_definition = await db.scalar(
            select(InterviewDefinition).where(
                InterviewDefinition.id == interview_definition_id,
                InterviewDefinition.organization_id == organization_id,
            )
        )
        if interview_definition is None:
            raise ApplicationError(
                "Interview definition was not found in this organization",
                "INTERVIEW_DEFINITION_NOT_FOUND",
            )

        session = InterviewSession(
            organization_id=organization_id,
            interview_definition_id=interview_definition_id,
            candidate_id=candidate_id,
            status=InterviewSessionStatus.CREATED.value,
            current_turn=0,
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)

        return session

    @staticmethod
    async def get_session(
        db: AsyncSession,
        organization_id: UUID,
        session_id: UUID,
    ) -> InterviewSession:
        session = await db.scalar(
            select(InterviewSession).where(
                InterviewSession.id == session_id,
                InterviewSession.organization_id == organization_id,
            )
        )

        if session is None:
            raise ApplicationError(
                "Interview session was not found in this organization",
                "INTERVIEW_SESSION_NOT_FOUND",
            )

        return session

    @staticmethod
    async def start_session(
        db: AsyncSession,
        organization_id: UUID,
        session_id: UUID,
    ) -> InterviewSession:
        session = await InterviewSessionService.get_session(
            db=db,
            organization_id=organization_id,
            session_id=session_id,
        )

        if session.status != InterviewSessionStatus.CREATED.value:
            raise ApplicationError(
                f"Cannot start session with status '{session.status}'. Only CREATED sessions can be started.",
                "INVALID_SESSION_TRANSITION",
            )

        session.status = InterviewSessionStatus.IN_PROGRESS.value
        session.started_at = datetime.now(timezone.utc)
        session.current_turn = 0

        await db.commit()
        await db.refresh(session)

        return session

    @staticmethod
    async def advance_turn(
        db: AsyncSession,
        organization_id: UUID,
        session_id: UUID,
    ) -> InterviewSession:
        session = await InterviewSessionService.get_session(
            db=db,
            organization_id=organization_id,
            session_id=session_id,
        )

        if session.status != InterviewSessionStatus.IN_PROGRESS.value:
            raise ApplicationError(
                f"Cannot advance turn for session with status '{session.status}'. Only IN_PROGRESS sessions can advance turns.",
                "INVALID_SESSION_TRANSITION",
            )

        if session.current_turn < 0:
            raise ApplicationError(
                "Current turn cannot be negative",
                "INVALID_SESSION_STATUS",
            )

        session.current_turn += 1

        await db.commit()
        await db.refresh(session)

        return session

    @staticmethod
    async def complete_session(
        db: AsyncSession,
        organization_id: UUID,
        session_id: UUID,
    ) -> InterviewSession:
        session = await InterviewSessionService.get_session(
            db=db,
            organization_id=organization_id,
            session_id=session_id,
        )

        if session.status != InterviewSessionStatus.IN_PROGRESS.value:
            raise ApplicationError(
                f"Cannot complete session with status '{session.status}'. Only IN_PROGRESS sessions can be completed.",
                "INVALID_SESSION_TRANSITION",
            )

        session.status = InterviewSessionStatus.COMPLETED.value
        session.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(session)

        return session

    @staticmethod
    async def finalize_session(
        db: AsyncSession,
        organization_id: UUID,
        session_id: UUID,
    ) -> InterviewSession:
        session = await InterviewSessionService.get_session(
            db=db,
            organization_id=organization_id,
            session_id=session_id,
        )

        if session.status != InterviewSessionStatus.COMPLETED.value:
            raise ApplicationError(
                f"Cannot finalize session with status '{session.status}'. Only COMPLETED sessions can be finalized.",
                "INVALID_SESSION_TRANSITION",
            )

        session.status = InterviewSessionStatus.FINALIZED.value

        await db.commit()
        await db.refresh(session)

        return session
