from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.database.models.interview_session import (
    InterviewSession,
    InterviewSessionStatus,
)
from app.database.session import AsyncSessionLocal
from app.domain.adaptive_decision import AdaptiveAction, AdaptiveDecision
from app.domain.assessment_operations import (
    FinalizeAssessmentInput,
    FinalizeAssessmentResult,
)
from app.domain.response_evaluation import ResponseEvaluation
from app.interview.graph_state import InterviewGraphState
from app.interview.orchestrator import AdaptiveInterviewOrchestrator
from app.mcp.assessment_operations import AssessmentOperationsMCP
from app.services.candidate_service import CandidateService
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.interview_session_service import InterviewSessionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


# ---------------------------------------------------------------------------
# Test Fixtures & DB Helpers
# ---------------------------------------------------------------------------

async def setup_test_context(db):
    org = await OrganizationService.create_organization(
        db,
        name=f"MCP Test Org {uuid4().hex[:8]}",
        slug=f"mcp-org-{uuid4().hex[:8]}",
    )
    job = await JobService.create_job(
        db=db,
        organization_id=org.id,
        title="Site Reliability Engineer",
        description="Core infrastructure engineering",
        seniority_level="Senior",
    )
    interview_def = await InterviewDefinitionService.create_interview_definition(
        db=db,
        organization_id=org.id,
        job_id=job.id,
        name="Reliability Assessment",
    )
    candidate = await CandidateService.create_candidate(
        db=db,
        organization_id=org.id,
        name="Bob Candidate",
        email=f"bob-{uuid4().hex[:6]}@example.com",
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


# ---------------------------------------------------------------------------
# Unit Tests: MCP Tool Definitions & Protocol Boundaries
# ---------------------------------------------------------------------------

def test_mcp_tool_definitions_metadata():
    definitions = AssessmentOperationsMCP.get_tool_definitions()
    assert len(definitions) == 1
    tool = definitions[0]
    assert tool["name"] == "finalize_assessment"
    assert "authoritatively finalize" in tool["description"].lower()
    assert "properties" in tool["inputSchema"]
    assert "session_id" in tool["inputSchema"]["properties"]
    assert "organization_id" in tool["inputSchema"]["properties"]
    assert "reason" in tool["inputSchema"]["properties"]


@pytest.mark.asyncio
async def test_arbitrary_operations_forbidden():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        # Attempt to run arbitrary / fake tools
        for fake_tool in ["calculator", "get_weather", "execute_sql", "generic_query"]:
            res = await mcp.execute_tool(
                tool_name=fake_tool,
                arguments={"query": "SELECT * FROM users"},
                db=db,
            )
            assert res["isError"] is True
            assert res["result"] is None
            assert f"Tool '{fake_tool}' is not recognized or permitted" in res["content"][0]["text"]


# ---------------------------------------------------------------------------
# Integration Tests: Direct MCP Assessment Operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_finalization_from_completed():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)
            await InterviewSessionService.complete_session(db, org_id, session.id)

            input_payload = FinalizeAssessmentInput(
                session_id=session.id,
                organization_id=org_id,
                final_turn=8,
                reason="All competency evaluations concluded with sufficient evidence.",
            )

            result = await mcp.finalize_assessment(input_payload, db)

            assert result.success is True
            assert result.session_id == session.id
            assert result.organization_id == org_id
            assert result.previous_status == "COMPLETED"
            assert result.new_status == "FINALIZED"
            assert result.finalized_at is not None
            assert "successfully finalized" in result.message
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_valid_finalization_from_in_progress():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)

            input_payload = FinalizeAssessmentInput(
                session_id=session.id,
                organization_id=org_id,
                final_turn=10,
                reason="Turn limit reached during LangGraph execution.",
            )

            result = await mcp.finalize_assessment(input_payload, db)

            assert result.success is True
            assert result.previous_status == "IN_PROGRESS"
            assert result.new_status == "FINALIZED"
            assert result.finalized_at is not None
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_invalid_session_not_found():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, _, _ = await setup_test_context(db)
        org_id = org.id
        try:
            non_existent_id = uuid4()
            result = await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=non_existent_id,
                    organization_id=org_id,
                    reason="Concluding non-existent session.",
                ),
                db=db,
            )
            assert result.success is False
            assert result.error_code == "INTERVIEW_SESSION_NOT_FOUND"
            assert "not found" in result.message.lower()
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_wrong_organization_rejected():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org_a, _, interview_def, candidate = await setup_test_context(db)
        org_b = await OrganizationService.create_organization(
            db,
            name=f"Org B {uuid4().hex[:8]}",
            slug=f"org-b-{uuid4().hex[:8]}",
        )
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_a.id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )

            # Org B attempts to finalize Org A's session
            result = await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=session.id,
                    organization_id=org_b.id,
                    reason="Cross-tenant unauthorized finalize attempt.",
                ),
                db=db,
            )

            assert result.success is False
            assert result.error_code == "INTERVIEW_SESSION_NOT_FOUND"
        finally:
            await cleanup_test_context(db, [org_a.id, org_b.id])


@pytest.mark.asyncio
async def test_invalid_state_transition_created():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            # Session is in CREATED status
            assert session.status == InterviewSessionStatus.CREATED.value

            result = await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=session.id,
                    organization_id=org_id,
                    reason="Attempting to finalize newly created session.",
                ),
                db=db,
            )

            assert result.success is False
            assert result.error_code == "INVALID_SESSION_TRANSITION"
            assert "CREATED" in result.message
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_repeated_finalization_rejected():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)

            # First finalization
            res1 = await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=session.id,
                    organization_id=org_id,
                    reason="First valid finalization.",
                ),
                db=db,
            )
            assert res1.success is True

            # Repeated finalization
            res2 = await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=session.id,
                    organization_id=org_id,
                    reason="Repeated second finalization.",
                ),
                db=db,
            )
            assert res2.success is False
            assert res2.error_code == "ALREADY_FINALIZED"
            assert "already finalized" in res2.message.lower()
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_mcp_protocol_execute_tool_interface():
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)

            payload = {
                "session_id": str(session.id),
                "organization_id": str(org_id),
                "final_turn": 5,
                "reason": "Protocol-compliant finalization.",
            }

            response = await mcp.execute_tool(
                tool_name="finalize_assessment",
                arguments=payload,
                db=db,
            )

            assert response["isError"] is False
            assert len(response["content"]) == 1
            assert response["content"][0]["type"] == "text"
            assert "successfully finalized" in response["content"][0]["text"]
            assert response["result"]["new_status"] == "FINALIZED"
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_independent_database_verification():
    """Verify that independent DB query confirms persisted state change to FINALIZED."""
    mcp = AssessmentOperationsMCP()
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)

            await mcp.finalize_assessment(
                FinalizeAssessmentInput(
                    session_id=session.id,
                    organization_id=org_id,
                    final_turn=7,
                    reason="Independent verification test.",
                ),
                db=db,
            )

            # Independent query through fresh DB lookup
            persisted = await db.scalar(
                select(InterviewSession).where(InterviewSession.id == session.id)
            )
            assert persisted is not None
            assert persisted.status == InterviewSessionStatus.FINALIZED.value
            assert persisted.current_turn == 7
            assert persisted.completed_at is not None
        finally:
            await cleanup_test_context(db, [org_id])


# ---------------------------------------------------------------------------
# Integration Tests: LangGraph COMPLETE Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_langgraph_complete_integration_with_db():
    async with AsyncSessionLocal() as db:
        org, _, interview_def, candidate = await setup_test_context(db)
        org_id = org.id
        try:
            session = await InterviewSessionService.create_session(
                db=db,
                organization_id=org_id,
                interview_definition_id=interview_def.id,
                candidate_id=candidate.id,
            )
            await InterviewSessionService.start_session(db, org_id, session.id)

            comp_id = uuid4()
            comp = SimpleNamespace(id=comp_id, name="Cloud Architecture")
            q = SimpleNamespace(id=uuid4(), difficulty_level=3, competency_id=comp_id, question_text="Explain cloud resilience.")

            # Create mock response service returning strong evaluation
            mock_eval = ResponseEvaluation(
                competency_id=comp_id,
                evidence_summary="Candidate demonstrates mastery across all competencies.",
                demonstrated_level=4,
                depth_score=4.5,
                relevance_score=4.5,
                technical_accuracy_score=4.5,
                confidence=0.95,
                strengths=["Multi-region active-active deployment"],
                gaps=[],
                is_off_topic=False,
            )
            mock_response_service = MagicMock()
            mock_response_service.evaluate_answer = AsyncMock(return_value=mock_eval)

            # Decision engine mock producing COMPLETE
            mock_decision = AdaptiveDecision(
                action=AdaptiveAction.COMPLETE,
                target_difficulty=None,
                target_competency_id=None,
                reason="All turn requirements and competency targets met.",
                based_on_turn=10,
                confidence=0.95,
            )
            mock_decision_engine = MagicMock()
            mock_decision_engine.decide.return_value = mock_decision

            orchestrator = AdaptiveInterviewOrchestrator(
                response_service=mock_response_service,
                decision_engine=mock_decision_engine,
                db=db,
            )

            state: InterviewGraphState = {
                "session_id": session.id,
                "organization_id": org_id,
                "candidate_response": "We deploy active-active clusters with geo-routing.",
                "current_question": q,
                "current_competency": comp,
                "current_difficulty": 3,
                "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=4, weight=1.0)],
                "current_turn": 10,
                "min_turns": 8,
                "max_turns": 12,
                "interview_status": "IN_PROGRESS",
            }

            result_state = await orchestrator.run_turn(state)

            assert result_state["interview_status"] == "COMPLETED"
            assert result_state["next_question"] is None
            assert result_state["assessment_finalized"] is True
            assert isinstance(result_state["finalization_result"], FinalizeAssessmentResult)
            assert result_state["finalization_result"].new_status == "FINALIZED"

            # Independent DB check
            await db.refresh(session)
            assert session.status == InterviewSessionStatus.FINALIZED.value
        finally:
            await cleanup_test_context(db, [org_id])


@pytest.mark.asyncio
async def test_langgraph_complete_offline_safe():
    """Verify that when db is None (offline execution), LangGraph completes safely."""
    comp_id = uuid4()
    comp = SimpleNamespace(id=comp_id, name="Cloud Architecture")
    q = SimpleNamespace(id=uuid4(), difficulty_level=3, competency_id=comp_id, question_text="Explain resilience.")

    mock_eval = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Good answer.",
        demonstrated_level=3,
        depth_score=3.5,
        relevance_score=4.0,
        technical_accuracy_score=3.5,
        confidence=0.9,
        strengths=["Clear answer"],
        gaps=[],
        is_off_topic=False,
    )
    mock_response_service = MagicMock()
    mock_response_service.evaluate_answer = AsyncMock(return_value=mock_eval)

    mock_decision = AdaptiveDecision(
        action=AdaptiveAction.COMPLETE,
        target_difficulty=None,
        target_competency_id=None,
        reason="Concluding interview without DB.",
        based_on_turn=5,
        confidence=0.9,
    )
    mock_decision_engine = MagicMock()
    mock_decision_engine.decide.return_value = mock_decision

    orchestrator = AdaptiveInterviewOrchestrator(
        response_service=mock_response_service,
        decision_engine=mock_decision_engine,
        db=None,  # Offline execution
    )

    state: InterviewGraphState = {
        "candidate_response": "We deploy multi-region clusters.",
        "current_question": q,
        "current_competency": comp,
        "current_difficulty": 3,
        "interview_competencies": [SimpleNamespace(competency_id=comp_id, competency=comp, target_level=3, weight=1.0)],
        "current_turn": 5,
        "min_turns": 5,
        "max_turns": 10,
        "interview_status": "IN_PROGRESS",
    }

    result = await orchestrator.run_turn(state)

    assert result["interview_status"] == "COMPLETED"
    assert result["next_question"] is None
    assert result["assessment_finalized"] is False
    assert result["finalization_result"] is None


def test_structured_response_success():
    sid = uuid4()
    oid = uuid4()
    now = datetime.now(timezone.utc)
    res = FinalizeAssessmentResult(
        success=True,
        session_id=sid,
        organization_id=oid,
        previous_status="COMPLETED",
        new_status="FINALIZED",
        finalized_at=now,
        message="Session successfully finalized.",
    )
    assert res.success is True
    assert res.session_id == sid
    assert res.organization_id == oid
    assert res.previous_status == "COMPLETED"
    assert res.new_status == "FINALIZED"
    assert res.finalized_at == now
    assert res.error_code is None


def test_structured_response_failure():
    sid = uuid4()
    oid = uuid4()
    res = FinalizeAssessmentResult(
        success=False,
        session_id=sid,
        organization_id=oid,
        previous_status="UNKNOWN",
        new_status="UNKNOWN",
        message="Session was not found.",
        error_code="INTERVIEW_SESSION_NOT_FOUND",
        error_detail="UUID not matched in tenant partition.",
    )
    assert res.success is False
    assert res.error_code == "INTERVIEW_SESSION_NOT_FOUND"
    assert res.error_detail == "UUID not matched in tenant partition."

