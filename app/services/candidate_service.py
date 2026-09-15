from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.candidate import Candidate
from app.database.models.organization import Organization


class CandidateService:
    """Application service for candidate lifecycle operations."""

    @staticmethod
    async def create_candidate(
        db: AsyncSession,
        organization_id: UUID,
        name: str,
        email: str,
        status: str = "active",
    ) -> Candidate:
        name = name.strip() if name else ""
        email = email.strip() if email else ""
        status = status.strip().lower() if status else "active"

        if not name:
            raise ApplicationError(
                "Candidate name cannot be empty",
                "INVALID_CANDIDATE_NAME",
            )

        if not email:
            raise ApplicationError(
                "Candidate email cannot be empty",
                "INVALID_CANDIDATE_EMAIL",
            )

        organization = await db.scalar(
            select(Organization).where(Organization.id == organization_id)
        )
        if organization is None:
            raise ApplicationError(
                "Organization was not found",
                "ORGANIZATION_NOT_FOUND",
            )

        candidate = Candidate(
            organization_id=organization_id,
            name=name,
            email=email,
            status=status,
        )

        db.add(candidate)
        await db.commit()
        await db.refresh(candidate)

        return candidate

    @staticmethod
    async def get_candidate(
        db: AsyncSession,
        organization_id: UUID,
        candidate_id: UUID,
    ) -> Candidate:
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

        return candidate
