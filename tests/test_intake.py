from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.schemas.intake import JobIntakeRequest
from app.database.models.intake_request import IntakeRequest
from app.database.models.interview_definition import InterviewDefinition
from app.database.models.job import Job
from app.database.models.organization import Organization
from app.database.session import AsyncSessionLocal
from app.services.intake_service import IntakeService


@pytest.mark.asyncio
async def test_create_job_from_intake():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Intake Test Organization",
            slug=f"intake-test-{uuid4().hex[:8]}",
            status="active",
        )
        db.add(organization)
        await db.flush()

        request = JobIntakeRequest(
            organization_id=organization.id,
            idempotency_key=f"intake-test-{uuid4().hex}",
            job_title="Python Backend Developer",
            job_description="Build Python backend APIs.",
            seniority_level="mid",
            interview_name="Python Backend Interview",
        )

        job_id, interview_id, idempotent = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request,
            )
        )

        assert job_id is not None
        assert interview_id is not None
        assert idempotent is False

        job = await db.get(Job, job_id)
        interview = await db.get(
            InterviewDefinition,
            interview_id,
        )

        assert job is not None
        assert job.organization_id == organization.id
        assert job.title == "Python Backend Developer"

        assert interview is not None
        assert interview.organization_id == organization.id
        assert interview.job_id == job.id

        intake_result = await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.organization_id == organization.id,
                IntakeRequest.idempotency_key == request.idempotency_key,
            )
        )

        intake_record = intake_result.scalar_one()

        await db.delete(intake_record)
        await db.delete(interview)
        await db.delete(job)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_existing_resources():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Idempotency Test Organization",
            slug=f"idempotency-test-{uuid4().hex[:8]}",
            status="active",
        )
        db.add(organization)
        await db.flush()

        request = JobIntakeRequest(
            organization_id=organization.id,
            idempotency_key=f"same-request-{uuid4().hex}",
            job_title="Data Analyst",
            job_description="Analyze business data.",
            seniority_level="junior",
            interview_name="Data Analyst Interview",
        )

        first_job_id, first_interview_id, first_idempotent = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request,
            )
        )

        second_job_id, second_interview_id, second_idempotent = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request,
            )
        )

        # Same request must return the original resources.
        assert first_idempotent is False
        assert second_idempotent is True

        assert second_job_id == first_job_id
        assert second_interview_id == first_interview_id

        # Verify the persisted intake record using a fresh session.
        async with AsyncSessionLocal() as verify_db:
            intake_result = await verify_db.execute(
                select(IntakeRequest).where(
                    IntakeRequest.organization_id == organization.id,
                    IntakeRequest.idempotency_key == request.idempotency_key,
                )
            )

            intake_record = intake_result.scalar_one()

            assert intake_record.job_id == first_job_id
            assert (
                intake_record.interview_definition_id
                == first_interview_id
            )
            assert intake_record.status == "created"

            jobs_result = await verify_db.execute(
                select(Job).where(
                    Job.organization_id == organization.id,
                )
            )

            assert len(jobs_result.scalars().all()) == 1

            interviews_result = await verify_db.execute(
                select(InterviewDefinition).where(
                    InterviewDefinition.organization_id == organization.id,
                )
            )

            assert len(interviews_result.scalars().all()) == 1

    # Cleanup in dependency-safe order.
    async with AsyncSessionLocal() as cleanup_db:
        intake_result = await cleanup_db.execute(
            select(IntakeRequest).where(
                IntakeRequest.organization_id == organization.id,
                IntakeRequest.idempotency_key == request.idempotency_key,
            )
        )

        intake_record = intake_result.scalar_one_or_none()

        if intake_record is not None:
            await cleanup_db.delete(intake_record)

        interview = await cleanup_db.get(
            InterviewDefinition,
            first_interview_id,
        )

        if interview is not None:
            await cleanup_db.delete(interview)

        job = await cleanup_db.get(
            Job,
            first_job_id,
        )

        if job is not None:
            await cleanup_db.delete(job)

        organization_record = await cleanup_db.get(
            Organization,
            organization.id,
        )

        if organization_record is not None:
            await cleanup_db.delete(organization_record)

        await cleanup_db.commit()


@pytest.mark.asyncio
async def test_same_key_different_organizations_creates_separate_resources():
    async with AsyncSessionLocal() as db:
        organization_one = Organization(
            name="Organization One",
            slug=f"org-one-{uuid4().hex[:8]}",
            status="active",
        )

        organization_two = Organization(
            name="Organization Two",
            slug=f"org-two-{uuid4().hex[:8]}",
            status="active",
        )

        db.add_all(
            [
                organization_one,
                organization_two,
            ]
        )
        await db.flush()

        shared_key = f"shared-key-{uuid4().hex}"

        request_one = JobIntakeRequest(
            organization_id=organization_one.id,
            idempotency_key=shared_key,
            job_title="Backend Developer",
            job_description="Build backend services.",
            seniority_level="mid",
            interview_name="Backend Interview",
        )

        request_two = JobIntakeRequest(
            organization_id=organization_two.id,
            idempotency_key=shared_key,
            job_title="Frontend Developer",
            job_description="Build frontend applications.",
            seniority_level="mid",
            interview_name="Frontend Interview",
        )

        job_one, interview_one, idempotent_one = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request_one,
            )
        )

        job_two, interview_two, idempotent_two = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request_two,
            )
        )

        assert idempotent_one is False
        assert idempotent_two is False
        assert job_one != job_two

        intake_result = await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.organization_id.in_(
                    [
                        organization_one.id,
                        organization_two.id,
                    ]
                )
            )
        )

        intake_records = intake_result.scalars().all()

        assert len(intake_records) == 2

        for intake_record in intake_records:
            await db.delete(intake_record)

        interview_one_record = await db.get(
            InterviewDefinition,
            interview_one,
        )
        interview_two_record = await db.get(
            InterviewDefinition,
            interview_two,
        )

        job_one_record = await db.get(
            Job,
            job_one,
        )
        job_two_record = await db.get(
            Job,
            job_two,
        )

        await db.delete(interview_one_record)
        await db.delete(interview_two_record)
        await db.delete(job_one_record)
        await db.delete(job_two_record)
        await db.delete(organization_one)
        await db.delete(organization_two)
        await db.commit()


@pytest.mark.asyncio
async def test_intake_creates_persistent_intake_record():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Persistence Test Organization",
            slug=f"persistence-test-{uuid4().hex[:8]}",
            status="active",
        )
        db.add(organization)
        await db.flush()

        idempotency_key = f"persistent-key-{uuid4().hex}"

        request = JobIntakeRequest(
            organization_id=organization.id,
            idempotency_key=idempotency_key,
            job_title="ML Engineer",
            job_description="Build machine learning systems.",
            seniority_level="senior",
            interview_name="ML Engineer Interview",
        )

        job_id, interview_id, idempotent = (
            await IntakeService.create_job_from_intake(
                db=db,
                request=request,
            )
        )

        assert idempotent is False

        result = await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.organization_id == organization.id,
                IntakeRequest.idempotency_key == idempotency_key,
            )
        )

        intake_record = result.scalar_one()

        assert intake_record.job_id == job_id
        assert intake_record.interview_definition_id == interview_id
        assert intake_record.status == "created"

        interview = await db.get(
            InterviewDefinition,
            interview_id,
        )
        job = await db.get(
            Job,
            job_id,
        )

        await db.delete(intake_record)
        await db.delete(interview)
        await db.delete(job)
        await db.delete(organization)
        await db.commit()