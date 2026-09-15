from uuid import uuid4

import pytest

from app.database.models.interview_definition import InterviewDefinition
from app.database.models.job import Job
from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_create_interview_definition():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Interview Test Organization",
            slug=f"interview-org-{uuid4().hex[:8]}",
            status="active",
        )

        db.add(organization)
        await db.flush()

        job = Job(
            organization_id=organization.id,
            title="Python Engineer",
            description="Build backend applications.",
            seniority_level="mid",
            status="active",
        )

        db.add(job)
        await db.flush()

        interview = InterviewDefinition(
            organization_id=organization.id,
            job_id=job.id,
            name="Technical Interview",
            min_turns=8,
            max_turns=12,
            status="draft",
        )

        db.add(interview)
        await db.commit()
        await db.refresh(interview)

        assert interview.id is not None
        assert interview.organization_id == organization.id
        assert interview.job_id == job.id
        assert interview.name == "Technical Interview"
        assert interview.min_turns == 8
        assert interview.max_turns == 12
        assert interview.status == "draft"

        await db.delete(interview)
        await db.delete(job)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_interview_definition_is_scoped_to_same_organization():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Scoped Interview Organization",
            slug=f"scoped-interview-{uuid4().hex[:8]}",
            status="active",
        )

        db.add(organization)
        await db.flush()

        job = Job(
            organization_id=organization.id,
            title="Data Scientist",
            description="Build machine learning systems.",
            seniority_level="senior",
            status="active",
        )

        db.add(job)
        await db.flush()

        interview = InterviewDefinition(
            organization_id=organization.id,
            job_id=job.id,
            name="ML Technical Interview",
            min_turns=8,
            max_turns=10,
            status="draft",
        )

        db.add(interview)
        await db.commit()
        await db.refresh(interview)

        assert interview.organization_id == job.organization_id
        assert interview.job_id == job.id

        await db.delete(interview)
        await db.delete(job)
        await db.delete(organization)
        await db.commit()