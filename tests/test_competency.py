from uuid import uuid4

import pytest
from sqlalchemy import text

from app.database.session import AsyncSessionLocal
from app.services.competency_service import CompetencyService
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


async def create_test_interview(db):
    organization = await OrganizationService.create_organization(
        db,
        name=f"Competency Test Org {uuid4().hex[:8]}",
        slug=f"competency-test-{uuid4().hex[:8]}",
    )

    job = await JobService.create_job(
        db=db,
        organization_id=organization.id,
        title="Test Engineer",
        description="Test job for competency framework.",
        seniority_level="Senior",
    )

    interview = await InterviewDefinitionService.create_interview_definition(
        db=db,
        organization_id=organization.id,
        job_id=job.id,
        name="Technical Interview",
    )

    return organization, job, interview


async def cleanup_test_interview(db, organization_id):
    await db.execute(
        text(
            """
            DELETE FROM interview_competencies
            WHERE interview_definition_id IN (
                SELECT id FROM interview_definitions WHERE organization_id = :organization_id
            )
            OR competency_id IN (
                SELECT id FROM competencies WHERE organization_id = :organization_id
            )
            """
        ),
        {"organization_id": str(organization_id)},
    )
    await db.execute(
        text("DELETE FROM interview_definitions WHERE organization_id = :organization_id"),
        {"organization_id": str(organization_id)},
    )
    await db.execute(
        text("DELETE FROM jobs WHERE organization_id = :organization_id"),
        {"organization_id": str(organization_id)},
    )
    await db.execute(
        text("DELETE FROM competencies WHERE organization_id = :organization_id"),
        {"organization_id": str(organization_id)},
    )
    await db.execute(
        text("DELETE FROM organizations WHERE id = :organization_id"),
        {"organization_id": str(organization_id)},
    )
    await db.commit()


@pytest.mark.asyncio
async def test_create_competency():
    async with AsyncSessionLocal() as db:
        organization, _, _ = await create_test_interview(db)
        try:
            competency = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="Python",
                description="Ability to write and reason about Python code.",
            )

            assert competency.id is not None
            assert competency.organization_id == organization.id
            assert competency.name == "Python"
            assert competency.description == (
                "Ability to write and reason about Python code."
            )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_create_competency_rejects_blank_name():
    async with AsyncSessionLocal() as db:
        organization, _, _ = await create_test_interview(db)
        try:
            with pytest.raises(
                ValueError,
                match="Competency name cannot be blank",
            ):
                await CompetencyService().create_competency(
                    db=db,
                    organization_id=organization.id,
                    name="   ",
                    description="Some description",
                )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_create_competency_rejects_blank_description():
    async with AsyncSessionLocal() as db:
        organization, _, _ = await create_test_interview(db)
        try:
            with pytest.raises(
                ValueError,
                match="Competency description cannot be blank",
            ):
                await CompetencyService().create_competency(
                    db=db,
                    organization_id=organization.id,
                    name="Python",
                    description="   ",
                )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_get_competency_is_organization_scoped():
    async with AsyncSessionLocal() as db:
        organization, _, _ = await create_test_interview(db)
        try:
            competency = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="Problem Solving",
                description="Ability to solve unfamiliar technical problems.",
            )

            loaded = await CompetencyService().get_competency(
                db=db,
                organization_id=organization.id,
                competency_id=competency.id,
            )

            assert loaded.id == competency.id

            with pytest.raises(ValueError, match="Competency not found"):
                await CompetencyService().get_competency(
                    db=db,
                    organization_id=uuid4(),
                    competency_id=competency.id,
                )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_assign_competency_to_interview():
    async with AsyncSessionLocal() as db:
        organization, _, interview = await create_test_interview(db)
        try:
            competency = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="System Design",
                description="Ability to design scalable systems.",
            )

            assignment = await CompetencyService().assign_competency_to_interview(
                db=db,
                organization_id=organization.id,
                interview_definition_id=interview.id,
                competency_id=competency.id,
                weight=2.0,
                target_level=4,
                display_order=1,
            )

            assert assignment.id is not None
            assert assignment.interview_definition_id == interview.id
            assert assignment.competency_id == competency.id
            assert float(assignment.weight) == 2.0
            assert assignment.target_level == 4
            assert assignment.display_order == 1
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_assign_competency_rejects_invalid_configuration():
    async with AsyncSessionLocal() as db:
        organization, _, interview = await create_test_interview(db)
        try:
            competency = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="Communication",
                description="Ability to communicate technical ideas clearly.",
            )

            with pytest.raises(
                ValueError,
                match="Competency weight must be greater than zero",
            ):
                await CompetencyService().assign_competency_to_interview(
                    db=db,
                    organization_id=organization.id,
                    interview_definition_id=interview.id,
                    competency_id=competency.id,
                    weight=0,
                )

            with pytest.raises(
                ValueError,
                match="Target level must be between 1 and 5",
            ):
                await CompetencyService().assign_competency_to_interview(
                    db=db,
                    organization_id=organization.id,
                    interview_definition_id=interview.id,
                    competency_id=competency.id,
                    target_level=6,
                )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_assign_competency_enforces_organization_isolation():
    async with AsyncSessionLocal() as db:
        organization, _, interview = await create_test_interview(db)
        try:
            competency = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="Data Structures",
                description="Knowledge of fundamental data structures.",
            )

            with pytest.raises(
                ValueError,
                match="Interview definition not found",
            ):
                await CompetencyService().assign_competency_to_interview(
                    db=db,
                    organization_id=uuid4(),
                    interview_definition_id=interview.id,
                    competency_id=competency.id,
                )
        finally:
            await cleanup_test_interview(db, organization.id)


@pytest.mark.asyncio
async def test_list_interview_competencies_orders_by_display_order():
    async with AsyncSessionLocal() as db:
        organization, _, interview = await create_test_interview(db)
        try:
            python = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="Python",
                description="Python programming ability.",
            )

            system_design = await CompetencyService().create_competency(
                db=db,
                organization_id=organization.id,
                name="System Design",
                description="System architecture ability.",
            )

            await CompetencyService().assign_competency_to_interview(
                db=db,
                organization_id=organization.id,
                interview_definition_id=interview.id,
                competency_id=system_design.id,
                weight=2.0,
                target_level=4,
                display_order=2,
            )

            await CompetencyService().assign_competency_to_interview(
                db=db,
                organization_id=organization.id,
                interview_definition_id=interview.id,
                competency_id=python.id,
                weight=1.5,
                target_level=4,
                display_order=1,
            )

            assignments = await CompetencyService().list_interview_competencies(
                db=db,
                organization_id=organization.id,
                interview_definition_id=interview.id,
            )

            assert len(assignments) == 2
            assert assignments[0].competency_id == python.id
            assert assignments[1].competency_id == system_design.id
        finally:
            await cleanup_test_interview(db, organization.id)