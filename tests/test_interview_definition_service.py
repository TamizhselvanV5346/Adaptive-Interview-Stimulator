from uuid import uuid4

import pytest

from app.core.exceptions import ApplicationError
from app.database.models.job import Job
from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal
from app.services.interview_definition_service import (
    InterviewDefinitionService,
)


@pytest.mark.asyncio
async def test_create_interview_definition_service():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Interview Service Org",
            slug=f"interview-service-{uuid4().hex[:8]}",
            status="active",
        )
        db.add(organization)
        await db.flush()

        job = Job(
            organization_id=organization.id,
            title="AI Engineer",
            description="Build AI systems.",
            seniority_level="mid",
            status="active",
        )
        db.add(job)
        await db.flush()

        interview = await InterviewDefinitionService.create_interview_definition(
            db=db,
            organization_id=organization.id,
            job_id=job.id,
            name="Technical AI Interview",
        )

        assert interview.name == "Technical AI Interview"
        assert interview.min_turns == 8
        assert interview.max_turns == 12
        assert interview.job_id == job.id
        assert interview.organization_id == organization.id

        await db.delete(interview)
        await db.delete(job)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_interview_cannot_use_job_from_another_organization():
    async with AsyncSessionLocal() as db:
        organization_a = Organization(
            name="Organization A",
            slug=f"org-a-{uuid4().hex[:8]}",
            status="active",
        )

        organization_b = Organization(
            name="Organization B",
            slug=f"org-b-{uuid4().hex[:8]}",
            status="active",
        )

        db.add_all([organization_a, organization_b])
        await db.flush()

        job = Job(
            organization_id=organization_a.id,
            title="Private Job",
            description="Organization A job.",
            seniority_level="senior",
            status="active",
        )

        db.add(job)
        await db.commit()

        with pytest.raises(ApplicationError) as error:
            await InterviewDefinitionService.create_interview_definition(
                db=db,
                organization_id=organization_b.id,
                job_id=job.id,
                name="Unauthorized Interview",
            )

        assert error.value.code == "JOB_NOT_FOUND"

        await db.delete(job)
        await db.delete(organization_a)
        await db.delete(organization_b)
        await db.commit()