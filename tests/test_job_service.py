from uuid import uuid4

import pytest

from app.core.exceptions import ApplicationError
from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_create_job_service():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Job Service Org",
            slug=f"job-service-{uuid4().hex[:8]}",
            status="active",
        )
        db.add(organization)
        await db.flush()

        job = await JobService.create_job(
            db=db,
            organization_id=organization.id,
            title=" Python Engineer ",
            description=" Build backend services ",
            seniority_level=" Senior ",
        )

        assert job.title == "Python Engineer"
        assert job.description == "Build backend services"
        assert job.seniority_level == "senior"
        assert job.organization_id == organization.id

        await db.delete(job)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_empty_job_title_rejected():
    async with AsyncSessionLocal() as db:
        with pytest.raises(ApplicationError) as error:
            await JobService.create_job(
                db=db,
                organization_id=uuid4(),
                title="",
                description="Valid description",
                seniority_level="junior",
            )

        assert error.value.code == "INVALID_JOB_TITLE"