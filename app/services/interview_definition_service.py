from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.database.models.interview_definition import InterviewDefinition
from app.database.models.job import Job


class InterviewDefinitionService:
    """Application service for interview definition lifecycle operations."""

    @staticmethod
    async def create_interview_definition(
        db: AsyncSession,
        organization_id: UUID,
        job_id: UUID,
        name: str,
        min_turns: int | None = None,
        max_turns: int | None = None,
    ) -> InterviewDefinition:
        name = name.strip()

        if not name:
            raise ApplicationError(
                "Interview name cannot be empty",
                "INVALID_INTERVIEW_NAME",
            )

        job = await db.scalar(
            select(Job).where(
                Job.id == job_id,
                Job.organization_id == organization_id,
            )
        )

        if job is None:
            raise ApplicationError(
                "Job was not found in this organization",
                "JOB_NOT_FOUND",
            )

        resolved_min_turns = (
            settings.min_interview_turns
            if min_turns is None
            else min_turns
        )

        resolved_max_turns = (
            settings.max_interview_turns
            if max_turns is None
            else max_turns
        )

        if resolved_min_turns < 8:
            raise ApplicationError(
                "Minimum interview turns cannot be less than 8",
                "INVALID_MIN_TURNS",
            )

        if resolved_max_turns < resolved_min_turns:
            raise ApplicationError(
                "Maximum interview turns cannot be less than minimum turns",
                "INVALID_TURN_RANGE",
            )

        interview = InterviewDefinition(
            organization_id=organization_id,
            job_id=job_id,
            name=name,
            min_turns=resolved_min_turns,
            max_turns=resolved_max_turns,
            status="draft",
        )

        db.add(interview)
        await db.commit()
        await db.refresh(interview)

        return interview