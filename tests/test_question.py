from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.exceptions import ApplicationError
from app.database.models.question import QuestionType
from app.database.session import AsyncSessionLocal
from app.interview.question_selector import QuestionSelector
from app.services.competency_service import CompetencyService
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService
from app.services.question_service import QuestionService


async def setup_test_context(db):
    org = await OrganizationService.create_organization(
        db,
        name=f"Question Test Org {uuid4().hex[:8]}",
        slug=f"question-org-{uuid4().hex[:8]}",
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
        name="Technical Interview",
    )
    competency = await CompetencyService().create_competency(
        db=db,
        organization_id=org.id,
        name="Algorithms",
        description="Data structures and algorithmic problem solving",
    )
    await CompetencyService().assign_competency_to_interview(
        db=db,
        organization_id=org.id,
        interview_definition_id=interview_def.id,
        competency_id=competency.id,
        weight=1.5,
        target_level=3,
        display_order=1,
    )
    return org, job, interview_def, competency


async def cleanup_test_context(db, organization_ids: list[UUID]):
    for org_id in organization_ids:
        await db.execute(
            text("DELETE FROM questions WHERE organization_id = :org_id"),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text(
                """
                DELETE FROM interview_competencies
                WHERE interview_definition_id IN (
                    SELECT id FROM interview_definitions WHERE organization_id = :org_id
                )
                OR competency_id IN (
                    SELECT id FROM competencies WHERE organization_id = :org_id
                )
                """
            ),
            {"org_id": str(org_id)},
        )
        await db.execute(
            text("DELETE FROM competencies WHERE organization_id = :org_id"),
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
async def test_create_question():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            question = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Explain how hash maps handle collisions.",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=3,
                expected_signal="Understanding of chaining vs open addressing.",
                display_order=1,
            )

            assert question.id is not None
            assert question.organization_id == org_id
            assert question.interview_definition_id == interview_def_id
            assert question.competency_id == competency_id
            assert question.question_text == "Explain how hash maps handle collisions."
            assert question.question_type == QuestionType.TECHNICAL.value
            assert question.difficulty_level == 3
            assert question.expected_signal == "Understanding of chaining vs open addressing."
            assert question.display_order == 1
            assert question.is_active is True
            assert question.created_at is not None
            assert question.updated_at is not None
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_blank_question_rejected():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=competency_id,
                    question_text="   ",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=3,
                    expected_signal="Valid expected signal",
                )
            assert exc_info.value.code == "INVALID_QUESTION_TEXT"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_blank_expected_signal_rejected():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=competency_id,
                    question_text="Valid question text",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=3,
                    expected_signal="   ",
                )
            assert exc_info.value.code == "INVALID_EXPECTED_SIGNAL"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_difficulty_rejected():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            with pytest.raises(ApplicationError) as exc_low:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=competency_id,
                    question_text="Valid question text",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=0,
                    expected_signal="Valid expected signal",
                )
            assert exc_low.value.code == "INVALID_DIFFICULTY_LEVEL"

            with pytest.raises(ApplicationError) as exc_high:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=competency_id,
                    question_text="Valid question text",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=6,
                    expected_signal="Valid expected signal",
                )
            assert exc_high.value.code == "INVALID_DIFFICULTY_LEVEL"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_display_order_rejected():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=competency_id,
                    question_text="Valid question text",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=3,
                    expected_signal="Valid expected signal",
                    display_order=0,
                )
            assert exc_info.value.code == "INVALID_DISPLAY_ORDER"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_question_retrieval():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            created = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Explain async/await in Python.",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Event loop familiarity",
            )
            question_id = created.id

            loaded = await QuestionService.get_question(
                db=db,
                organization_id=org_id,
                question_id=question_id,
            )

            assert loaded.id == question_id
            assert loaded.question_text == created.question_text
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_organization_isolation():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        other_org_id = uuid4()
        try:
            created = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Explain database transactions.",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=3,
                expected_signal="ACID guarantees",
            )
            question_id = created.id

            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.get_question(
                    db=db,
                    organization_id=other_org_id,
                    question_id=question_id,
                )
            assert exc_info.value.code == "QUESTION_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_interview_definition_organization_isolation():
    async with AsyncSessionLocal() as db:
        org_a, _, _, comp_a = await setup_test_context(db)
        org_b, _, interview_def_b, _ = await setup_test_context(db)
        org_a_id = org_a.id
        org_b_id = org_b.id
        interview_def_b_id = interview_def_b.id
        comp_a_id = comp_a.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_a_id,
                    interview_definition_id=interview_def_b_id,
                    competency_id=comp_a_id,
                    question_text="Cross-org interview definition question.",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=2,
                    expected_signal="Should fail validation",
                )
            assert exc_info.value.code == "INTERVIEW_DEFINITION_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_a_id, org_b_id])


@pytest.mark.asyncio
async def test_competency_organization_isolation():
    async with AsyncSessionLocal() as db:
        org_a, _, interview_def_a, _ = await setup_test_context(db)
        org_b, _, _, comp_b = await setup_test_context(db)
        org_a_id = org_a.id
        org_b_id = org_b.id
        interview_def_a_id = interview_def_a.id
        comp_b_id = comp_b.id
        try:
            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_a_id,
                    interview_definition_id=interview_def_a_id,
                    competency_id=comp_b_id,
                    question_text="Cross-org competency question.",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=2,
                    expected_signal="Should fail validation",
                )
            assert exc_info.value.code == "COMPETENCY_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_a_id, org_b_id])


@pytest.mark.asyncio
async def test_competency_must_belong_to_interview_definition():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, _ = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        try:
            unassigned_competency = await CompetencyService().create_competency(
                db=db,
                organization_id=org_id,
                name="Unassigned Competency",
                description="Not linked to the interview definition",
            )
            unassigned_id = unassigned_competency.id

            with pytest.raises(ApplicationError) as exc_info:
                await QuestionService.create_question(
                    db=db,
                    organization_id=org_id,
                    interview_definition_id=interview_def_id,
                    competency_id=unassigned_id,
                    question_text="Question with unassigned competency",
                    question_type=QuestionType.TECHNICAL,
                    difficulty_level=2,
                    expected_signal="Rejection of unlinked competency",
                )
            assert exc_info.value.code == "COMPETENCY_NOT_ASSIGNED_TO_INTERVIEW"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_list_active_questions():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            q1 = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Active Question 1",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=1,
                expected_signal="Signal 1",
                display_order=1,
            )
            q2 = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Active Question 2",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Signal 2",
                display_order=2,
            )

            questions = await QuestionService.list_questions_for_interview(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
            )

            assert len(questions) == 2
            ids = [q.id for q in questions]
            assert q1.id in ids
            assert q2.id in ids
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_inactive_questions_excluded():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            q_active = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Active Question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=1,
                expected_signal="Active signal",
                is_active=True,
            )
            q_inactive = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Inactive Question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=1,
                expected_signal="Inactive signal",
                is_active=False,
            )

            # Default excludes inactive
            active_list = await QuestionService.list_questions_for_interview(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
            )
            assert len(active_list) == 1
            assert active_list[0].id == q_active.id

            # When include_inactive=True, both are returned
            all_list = await QuestionService.list_questions_for_interview(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                include_inactive=True,
            )
            assert len(all_list) == 2
            all_ids = [q.id for q in all_list]
            assert q_active.id in all_ids
            assert q_inactive.id in all_ids
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_deactivate_question():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            question = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Will be deactivated",
                question_type=QuestionType.BEHAVIORAL,
                difficulty_level=2,
                expected_signal="Signal",
                is_active=True,
            )
            q_id = question.id

            deactivated = await QuestionService.deactivate_question(
                db=db,
                organization_id=org_id,
                question_id=q_id,
            )
            assert deactivated.is_active is False

            loaded = await QuestionService.get_question(
                db=db,
                organization_id=org_id,
                question_id=q_id,
            )
            assert loaded.is_active is False
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_activate_question():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            question = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Will be activated",
                question_type=QuestionType.BEHAVIORAL,
                difficulty_level=2,
                expected_signal="Signal",
                is_active=False,
            )
            q_id = question.id

            activated = await QuestionService.activate_question(
                db=db,
                organization_id=org_id,
                question_id=q_id,
            )
            assert activated.is_active is True

            loaded = await QuestionService.get_question(
                db=db,
                organization_id=org_id,
                question_id=q_id,
            )
            assert loaded.is_active is True
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_deterministic_selector_returns_eligible_question():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            created = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Sample interview question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=3,
                expected_signal="Expected signal",
            )

            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
            )

            assert selected is not None
            assert selected.id == created.id
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_selector_excludes_used_questions():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            q1 = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Question 1",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Signal 1",
                display_order=1,
            )
            q2 = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Question 2",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Signal 2",
                display_order=2,
            )

            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
                used_question_ids={q1.id},
            )

            assert selected is not None
            assert selected.id == q2.id
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_selector_respects_competency():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, comp_a = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        comp_a_id = comp_a.id
        try:
            comp_b = await CompetencyService().create_competency(
                db=db,
                organization_id=org_id,
                name="System Architecture",
                description="Distributed systems design",
            )
            comp_b_id = comp_b.id
            await CompetencyService().assign_competency_to_interview(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=comp_b_id,
                weight=1.0,
                target_level=4,
                display_order=2,
            )

            q_a = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=comp_a_id,
                question_text="Algorithms question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Algo signal",
                display_order=1,
            )
            q_b = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=comp_b_id,
                question_text="System design question",
                question_type=QuestionType.SCENARIO,
                difficulty_level=2,
                expected_signal="Architecture signal",
                display_order=2,
            )

            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
                competency_id=comp_b_id,
            )

            assert selected is not None
            assert selected.id == q_b.id
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_selector_respects_difficulty():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            q_easy = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Easy question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=1,
                expected_signal="Basic signal",
                display_order=1,
            )
            q_hard = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Hard question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=5,
                expected_signal="Advanced signal",
                display_order=2,
            )

            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
                difficulty_level=5,
            )

            assert selected is not None
            assert selected.id == q_hard.id
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_selector_follows_display_order():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            q_second = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Second in line",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=3,
                expected_signal="Signal",
                display_order=2,
            )
            q_first = await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="First in line",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=3,
                expected_signal="Signal",
                display_order=1,
            )

            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
            )

            assert selected is not None
            assert selected.id == q_first.id
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_selector_returns_no_result_when_no_eligible_question_exists():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, competency = await setup_test_context(db)
        org_id = org.id
        interview_def_id = interview_def.id
        competency_id = competency.id
        try:
            await QuestionService.create_question(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def_id,
                competency_id=competency_id,
                question_text="Only difficulty 2 question",
                question_type=QuestionType.TECHNICAL,
                difficulty_level=2,
                expected_signal="Signal",
            )

            # Requesting difficulty 5 when none exists
            selected = await QuestionSelector.select_next_question(
                db=db,
                interview_definition_id=interview_def_id,
                organization_id=org_id,
                difficulty_level=5,
            )

            assert selected is None
        finally:
            await cleanup_test_context(db, [org_id])
