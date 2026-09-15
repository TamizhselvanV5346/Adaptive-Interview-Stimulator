from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.intake import (
    JobIntakeRequest,
    JobIntakeResponse,
)
from app.database.dependencies import get_db
from app.services.intake_service import IntakeService

router = APIRouter(
    prefix="/intake",
    tags=["Intake"],
)


@router.post(
    "/jobs",
    response_model=JobIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_from_intake(
    request: JobIntakeRequest,
    db: AsyncSession = Depends(get_db),
) -> JobIntakeResponse:
    """Create a job and interview definition from external intake."""

    job_id, interview_definition_id, idempotent = (
        await IntakeService.create_job_from_intake(
            db=db,
            request=request,
        )
    )

    return JobIntakeResponse(
        organization_id=request.organization_id,
        job_id=job_id,
        interview_definition_id=interview_definition_id,
        status="created",
        idempotent=idempotent,
    )