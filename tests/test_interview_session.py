from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ApplicationError
from app.database.models.interview_session import InterviewSessionStatus
from app.database.session import AsyncSessionLocal
from app.services.candidate_service import CandidateService
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.interview_session_service import InterviewSessionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


async def setup_test_context(db):
    org = await OrganizationService.create_organization(
        db,
        name=f"Session Test Org {uuid4().hex[:8]}",
        slug=f"session-org-{uuid4().hex[:8]}",
    )
    job = await JobService.create_job(
        db=db,
        organization_id=org.id,
        title="Software Engineer",
        description="Backend engineering role",
        seniority_level="Senior",
    )
    interview_def = await InterviewDefinitionService.create_interview_definition(
        db=db,
        organization_id=org.id,
        job_id=job.id,
        name="Backend Technical Interview",
    )
    candidate = await CandidateService.create_candidate(
        db=db,
        organization_id=org.id,
        name="Alice Candidate",
        email=f"alice-{uuid4().hex[:6]}@example.com",
    )
    return org, job, interview_def, candidate


async def cleanup_test_context(db, organization_ids: list[UUID]):
    for org_id in organization_ids:
        await db.execute(
            text("DELETE FROM interview_sessions WHERE organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text("DELETE FROM candidates WHERE organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text("DELETE FROM interview_definitions WHERE organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text("DELETE FROM jobs WHERE organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text("DELETE FROM organizations WHERE id = :org_id"),
            {"org_id": str(org_id)},
        )
    await db.commit()


@pytest.mark.asyncio
async def test_candidate_creation():
    async with AsyncSessionLocal() as db:
        org, _, _, _ = await setup_test_context(db)
        org_id = org.id
        try:
            candidate = await CandidateService.create_candidate(
                db=db,
                organization_id=org_id,
                name="John Doe",
                email="john.doe@example.com",
            )

            assert candidate.id is not None
            assert candidate.organization_id == org_id
            assert candidate.name == "John Doe"
            assert candidate.email == "john.doe@example.com"
            assert candidate.status == "active"
            assert candidate.created_at is not None
            assert candidate.updated_at is not None
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_candidate_retrieval():
    async with AsyncSessionLocal() as db:
        org, _, _, candidate = await setup_test_context(db)
        org_id = org.id
        candidate_id = candidate.id
        candidate_name = candidate.name
        candidate_email = candidate.email
        try:
            loaded = await CandidateService.get_candidate(
                db=db,
                organization_id=org_id,
                candidate_id=candidate_id,
            )

            assert loaded.id == candidate_id
            assert loaded.name == candidate_name
            assert loaded.email == candidate_email
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_candidate_organization_isolation():
    async with AsyncSessionLocal() as db:
        org, _, _, candidate = await setup_test_context(db)
        org_id = org.id
        candidate_id = candidate.id
        other_org_id = uuid4()
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await CandidateService.get_candidate(
                    db=db,
                    organization_id=other_org_id,
                    candidate_id=candidate_id,
                )

            assert exc_info.value.code == "CANDIDATE_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_session_creation():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )

            assert session.id is not None
            assert session.organization_id == org_id
            assert session.interview_definition_id == interview_def_id
            assert session.candidate_id == candidate_id
            assert session.status == InterviewSessionStatus.CREATED.value
            assert session.current_turn == 0
            assert session.started_at is None
            assert session.completed_at is None
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_session_starts_with_current_turn_zero():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )

            assert session.current_turn == 0
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_cross_organization_candidate_rejected():
    async with AsyncSessionLocal() as db:
        org_a, _, interview_def_a, _ = await setup_test_context(db)
        org_b, _, _, candidate_b = await setup_test_context(db)
        org_a_id = org_a.id
        org_b_id = org_b.id
        interview_def_a_id = interview_def_a.id
        candidate_b_id = candidate_b.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.create_session(
                    db=db,
                    organization_id=org_a_id,
                    interview_definition_id=interview_def_a_id,
                    candidate_id=candidate_b_id,
                )

            assert exc_info.value.code == "CANDIDATE_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_a_id, org_b_id])


@pytest.mark.asyncio
async def test_cross_organization_interview_definition_rejected():
    async with AsyncSessionLocal() as db:
        org_a, _, _, candidate_a = await setup_test_context(db)
        org_b, _, interview_def_b, _ = await setup_test_context(db)
        org_a_id = org_a.id
        org_b_id = org_b.id
        interview_def_b_id = interview_def_b.id
        candidate_a_id = candidate_a.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.create_session(
                    db=db,
                    organization_id=org_a_id,
                    interview_definition_id=interview_def_b_id,
                    candidate_id=candidate_a_id,
                )

            assert exc_info.value.code == "INTERVIEW_DEFINITION_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_a_id, org_b_id])


@pytest.mark.asyncio
async def test_session_retrieval_organization_isolation():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        other_org_id = uuid4()
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.get_session(
                    db=db,
                    organization_id=other_org_id,
                    session_id=session_id,
                )

            assert exc_info.value.code == "INTERVIEW_SESSION_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_created_to_in_progress_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )

            started = await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session.id,
            )

            assert started.status == InterviewSessionStatus.IN_PROGRESS.value
            assert started.started_at is not None
            assert started.current_turn == 0
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_start_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            # Attempting to start an already IN_PROGRESS session
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.start_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"

            # Attempting to start a COMPLETED session
            await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.start_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_advance_turn_increments_correctly():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            turn1 = await InterviewSessionService.advance_turn(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            assert turn1.current_turn == 1

            turn2 = await InterviewSessionService.advance_turn(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            assert turn2.current_turn == 2
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_cannot_advance_turn_after_completion():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.advance_turn(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.advance_turn(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )

            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_in_progress_to_completed_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            completed = await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            assert completed.status == InterviewSessionStatus.COMPLETED.value
            assert completed.completed_at is not None
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_completion_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            # Cannot complete a CREATED session
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.complete_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"

            # Transition to COMPLETED then FINALIZED
            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.finalize_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            # Cannot complete an already FINALIZED session
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.complete_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_completed_to_finalized_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            finalized = await InterviewSessionService.finalize_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            assert finalized.status == InterviewSessionStatus.FINALIZED.value
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_finalization_transition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            # Cannot finalize CREATED session
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.finalize_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"

            # Cannot finalize IN_PROGRESS session
            await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.finalize_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"

            # Transition to COMPLETED and then FINALIZED
            await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            await InterviewSessionService.finalize_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )

            # Cannot finalize already FINALIZED session
            with pytest.raises(ApplicationError) as exc_info:
                await InterviewSessionService.finalize_session(
                    db=db,
                    organization_id=org_id,
                    session_id=session_id,
                )
            assert exc_info.value.code == "INVALID_SESSION_TRANSITION"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_session_timestamps_populated_appropriately():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            session_id = session.id

            assert session.created_at is not None
            assert session.updated_at is not None
            assert session.started_at is None
            assert session.completed_at is None

            started = await InterviewSessionService.start_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            assert started.started_at is not None
            assert started.started_at.tzinfo is not None

            completed = await InterviewSessionService.complete_session(
                db=db,
                organization_id=org_id,
                session_id=session_id,
            )
            assert completed.completed_at is not None
            assert completed.completed_at.tzinfo is not None
            assert completed.started_at <= completed.completed_at
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_current_turn_never_becomes_negative():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        candidate_id = candidate.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                candidate_id=candidate_id,
            )
            assert session.current_turn >= 0

            # Attempt to set negative turn directly in database triggers CheckConstraint
            session.current_turn = -1
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()
        finally:
            await cleanup_test_context(db, [org_id])
