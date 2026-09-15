from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.job import Job


class JobService:
    """Application service for job lifecycle operations."""

    @staticmethod
    async def create_job(
        db: AsyncSession,
        organization_id: UUID,
        title: str,
        description: str,
        seniority_level: str,
    ) -> Job:
        title = title.strip()
        description = description.strip()
        seniority_level = seniority_level.strip().lower()

        if not title:
            raise ApplicationError(
                "Job title cannot be empty",
                "INVALID_JOB_TITLE",
            )

        if not description:
            raise ApplicationError(
                "Job description cannot be empty",
                "INVALID_JOB_DESCRIPTION",
            )

        if not seniority_level:
            raise ApplicationError(
                "Seniority level cannot be empty",
                "INVALID_SENIORITY_LEVEL",
            )

        job = Job(
            organization_id=organization_id,
            title=title,
            description=description,
            seniority_level=seniority_level,
            status="active",
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        return job

    @staticmethod
    async def get_job(
        db: AsyncSession,
        organization_id: UUID,
        job_id: UUID,
    ) -> Job:
        job = await db.scalar(
            select(Job).where(
                Job.id == job_id,
                Job.organization_id == organization_id,
            )
        )

        if job is None:
            raise ApplicationError(
                "Job was not found",
                "JOB_NOT_FOUND",
            )

        return job