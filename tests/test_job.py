from uuid import uuid4

import pytest

from app.database.models.job import Job
from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_create_job():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Job Test Organization",
            slug=f"job-org-{uuid4().hex[:8]}",
            status="active",
        )

        db.add(organization)
        await db.flush()

        job = Job(
            organization_id=organization.id,
            title="Senior Python Engineer",
            description="Build backend services and APIs.",
            seniority_level="senior",
            status="active",
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        assert job.id is not None
        assert job.organization_id == organization.id
        assert job.title == "Senior Python Engineer"
        assert job.description == "Build backend services and APIs."
        assert job.seniority_level == "senior"
        assert job.status == "active"

        await db.delete(job)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_job_belongs_to_organization():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Tenant Job Organization",
            slug=f"tenant-job-{uuid4().hex[:8]}",
            status="active",
        )

        db.add(organization)
        await db.flush()

        job = Job(
            organization_id=organization.id,
            title="Data Analyst",
            description="Analyze business data.",
            seniority_level="junior",
            status="active",
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        assert job.organization_id == organization.id

        await db.delete(job)
        await db.delete(organization)
        await db.commit()