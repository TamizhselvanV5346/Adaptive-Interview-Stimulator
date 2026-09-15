from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.intake import JobIntakeRequest
from app.database.models.intake_request import IntakeRequest
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


class IntakeService:
    @staticmethod
    async def create_job_from_intake(
        db: AsyncSession,
        request: JobIntakeRequest,
    ) -> tuple[UUID, UUID, bool]:
        organization_service = OrganizationService()
        job_service = JobService()
        interview_service = InterviewDefinitionService()

        # Verify that the organization exists.
        await organization_service.get_organization(
            db,
            request.organization_id,
        )

        # Check whether this request has already been processed.
        existing_result = await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.organization_id == request.organization_id,
                IntakeRequest.idempotency_key == request.idempotency_key,
            )
        )
        existing_request = existing_result.scalar_one_or_none()

        if existing_request:
            return (
                existing_request.job_id,
                existing_request.interview_definition_id,
                True,
            )

        # Create the job.
        job = await job_service.create_job(
            db=db,
            organization_id=request.organization_id,
            title=request.job_title,
            description=request.job_description,
            seniority_level=request.seniority_level,
        )

        # Create the interview definition.
        interview_definition = (
            await interview_service.create_interview_definition(
                db=db,
                organization_id=request.organization_id,
                job_id=job.id,
                name=request.interview_name,
            )
        )

        # Persist the intake request and its resulting resources.
        intake_request = IntakeRequest(
            organization_id=request.organization_id,
            idempotency_key=request.idempotency_key,
            job_id=job.id,
            interview_definition_id=interview_definition.id,
            status="created",
        )

        db.add(intake_request)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

            # Another request may have created the same idempotency key
            # concurrently. Return the already-created resources.
            existing_result = await db.execute(
                select(IntakeRequest).where(
                    IntakeRequest.organization_id == request.organization_id,
                    IntakeRequest.idempotency_key
                    == request.idempotency_key,
                )
            )
            existing_request = existing_result.scalar_one()

            return (
                existing_request.job_id,
                existing_request.interview_definition_id,
                True,
            )

        return (
            job.id,
            interview_definition.id,
            False,
        )