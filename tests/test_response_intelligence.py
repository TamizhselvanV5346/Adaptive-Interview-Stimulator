from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.ai.providers.base import ResponseEvaluationProvider
from app.ai.providers.claude import ClaudeProvider
from app.ai.providers.mock import MockProvider
from app.ai.response_intelligence import ResponseIntelligenceService
from app.core.exceptions import ApplicationError
from app.database.models.question import QuestionType
from app.database.session import AsyncSessionLocal
from app.domain.response_evaluation import ResponseEvaluation
from app.services.candidate_response_service import CandidateResponseService
from app.services.candidate_service import CandidateService
from app.services.competency_service import CompetencyService
from app.services.interview_definition_service import InterviewDefinitionService
from app.services.interview_session_service import InterviewSessionService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService
from app.services.question_service import QuestionService


# ---------------------------------------------------------------------------
# 1-11: Contract and Domain Validation Tests
# ---------------------------------------------------------------------------

def test_valid_evaluation():
    """1. Valid evaluation object passes all contract validations."""
    comp_id = uuid4()
    eval_obj = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate clearly articulated the root cause and resolution steps.",
        strengths=["Systematic debugging approach", "Understood heap dump analysis"],
        gaps=["Did not explain post-mortem action items"],
        relevance_score=4.5,
        depth_score=4.0,
        technical_accuracy_score=4.5,
        confidence=0.9,
        demonstrated_level=4,
        is_off_topic=False,
        off_topic_reason=None,
    )
    assert eval_obj.competency_id == comp_id
    assert eval_obj.relevance_score == 4.5
    assert eval_obj.demonstrated_level == 4
    assert eval_obj.is_off_topic is False
    assert len(eval_obj.strengths) == 2


@pytest.mark.asyncio
async def test_blank_answer():
    """2. Blank answer is handled gracefully without crashing."""
    service = ResponseIntelligenceService(provider=MockProvider())
    comp_id = uuid4()
    eval_obj = await service.evaluate_answer(
        question="Describe a complex outage you resolved.",
        answer="",
        competency={"id": comp_id, "name": "Incident Management", "description": "Handling production issues"},
    )
    assert isinstance(eval_obj, ResponseEvaluation)
    assert eval_obj.competency_id == comp_id
    assert eval_obj.is_off_topic is True
    assert eval_obj.relevance_score == 0.0
    assert eval_obj.depth_score == 0.0
    assert eval_obj.technical_accuracy_score == 0.0
    assert eval_obj.demonstrated_level == 1
    assert "blank" in eval_obj.off_topic_reason.lower() or "empty" in eval_obj.off_topic_reason.lower()


@pytest.mark.asyncio
async def test_whitespace_answer():
    """3. Whitespace-only answer is handled gracefully without crashing."""
    service = ResponseIntelligenceService(provider=MockProvider())
    comp_id = uuid4()
    eval_obj = await service.evaluate_answer(
        question="What is the time complexity of quicksort?",
        answer="   \n\t  \r  ",
        competency={"id": comp_id, "name": "Algorithms", "description": "Sorting algorithms"},
    )
    assert isinstance(eval_obj, ResponseEvaluation)
    assert eval_obj.is_off_topic is True
    assert eval_obj.relevance_score == 0.0
    assert eval_obj.depth_score == 0.0
    assert eval_obj.demonstrated_level == 1


def test_score_validation():
    """4. Score validation verifies numerical types and standard score assignment."""
    comp_id = uuid4()
    eval_obj = ResponseEvaluation(
        competency_id=comp_id,
        evidence_summary="Candidate demonstrated foundational knowledge.",
        strengths=["Correct definition"],
        gaps=["No practical example"],
        relevance_score=3,
        depth_score=2,
        technical_accuracy_score=3,
        confidence=0.8,
        demonstrated_level=2,
        is_off_topic=False,
    )
    assert isinstance(eval_obj.relevance_score, float)
    assert isinstance(eval_obj.confidence, float)
    assert isinstance(eval_obj.demonstrated_level, int)


def test_relevance_bounds():
    """5. Relevance score must be strictly between 0 and 5."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "evidence_summary": "Valid summary",
        "strengths": ["Good"],
        "gaps": ["None"],
        "depth_score": 3.0,
        "technical_accuracy_score": 3.0,
        "confidence": 0.8,
        "demonstrated_level": 3,
        "is_off_topic": False,
    }

    # Below minimum
    with pytest.raises(ValidationError):
        ResponseEvaluation(relevance_score=-0.1, **base_kwargs)

    # Above maximum
    with pytest.raises(ValidationError):
        ResponseEvaluation(relevance_score=5.1, **base_kwargs)

    # Boundary edges
    assert ResponseEvaluation(relevance_score=0.0, **base_kwargs).relevance_score == 0.0
    assert ResponseEvaluation(relevance_score=5.0, **base_kwargs).relevance_score == 5.0


def test_depth_bounds():
    """6. Depth score must be strictly between 0 and 5."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "evidence_summary": "Valid summary",
        "strengths": ["Good"],
        "gaps": ["None"],
        "relevance_score": 3.0,
        "technical_accuracy_score": 3.0,
        "confidence": 0.8,
        "demonstrated_level": 3,
        "is_off_topic": False,
    }

    with pytest.raises(ValidationError):
        ResponseEvaluation(depth_score=-1.0, **base_kwargs)

    with pytest.raises(ValidationError):
        ResponseEvaluation(depth_score=5.5, **base_kwargs)

    assert ResponseEvaluation(depth_score=0.0, **base_kwargs).depth_score == 0.0
    assert ResponseEvaluation(depth_score=5.0, **base_kwargs).depth_score == 5.0


def test_technical_accuracy_bounds():
    """7. Technical accuracy score must be strictly between 0 and 5."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "evidence_summary": "Valid summary",
        "strengths": ["Good"],
        "gaps": ["None"],
        "relevance_score": 3.0,
        "depth_score": 3.0,
        "confidence": 0.8,
        "demonstrated_level": 3,
        "is_off_topic": False,
    }

    with pytest.raises(ValidationError):
        ResponseEvaluation(technical_accuracy_score=-0.01, **base_kwargs)

    with pytest.raises(ValidationError):
        ResponseEvaluation(technical_accuracy_score=5.01, **base_kwargs)

    assert ResponseEvaluation(technical_accuracy_score=0.0, **base_kwargs).technical_accuracy_score == 0.0
    assert ResponseEvaluation(technical_accuracy_score=5.0, **base_kwargs).technical_accuracy_score == 5.0


def test_confidence_bounds():
    """8. Confidence must be strictly between 0.0 and 1.0."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "evidence_summary": "Valid summary",
        "strengths": ["Good"],
        "gaps": ["None"],
        "relevance_score": 3.0,
        "depth_score": 3.0,
        "technical_accuracy_score": 3.0,
        "demonstrated_level": 3,
        "is_off_topic": False,
    }

    with pytest.raises(ValidationError):
        ResponseEvaluation(confidence=-0.1, **base_kwargs)

    with pytest.raises(ValidationError):
        ResponseEvaluation(confidence=1.1, **base_kwargs)

    assert ResponseEvaluation(confidence=0.0, **base_kwargs).confidence == 0.0
    assert ResponseEvaluation(confidence=1.0, **base_kwargs).confidence == 1.0


def test_demonstrated_level_bounds():
    """9. Demonstrated level must be an integer between 1 and 5."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "evidence_summary": "Valid summary",
        "strengths": ["Good"],
        "gaps": ["None"],
        "relevance_score": 3.0,
        "depth_score": 3.0,
        "technical_accuracy_score": 3.0,
        "confidence": 0.8,
        "is_off_topic": False,
    }

    with pytest.raises(ValidationError):
        ResponseEvaluation(demonstrated_level=0, **base_kwargs)

    with pytest.raises(ValidationError):
        ResponseEvaluation(demonstrated_level=6, **base_kwargs)

    # Reject boolean as int
    with pytest.raises(ValidationError):
        ResponseEvaluation(demonstrated_level=True, **base_kwargs)

    assert ResponseEvaluation(demonstrated_level=1, **base_kwargs).demonstrated_level == 1
    assert ResponseEvaluation(demonstrated_level=5, **base_kwargs).demonstrated_level == 5


def test_evidence_summary_and_string_lists_cannot_be_blank():
    """Validates that evidence_summary, strengths, and gaps cannot have blank strings."""
    comp_id = uuid4()
    base_kwargs = {
        "competency_id": comp_id,
        "relevance_score": 3.0,
        "depth_score": 3.0,
        "technical_accuracy_score": 3.0,
        "confidence": 0.8,
        "demonstrated_level": 3,
        "is_off_topic": False,
    }

    # Blank evidence summary
    with pytest.raises(ValidationError):
        ResponseEvaluation(evidence_summary="   ", strengths=["Clear"], gaps=[], **base_kwargs)

    # Blank item in strengths
    with pytest.raises(ValidationError):
        ResponseEvaluation(evidence_summary="Valid summary", strengths=["   "], gaps=[], **base_kwargs)

    # Blank item in gaps
    with pytest.raises(ValidationError):
        ResponseEvaluation(evidence_summary="Valid summary", strengths=[], gaps=["\t"], **base_kwargs)


# ---------------------------------------------------------------------------
# 10-14: Provider and Service Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_off_topic_evaluation():
    """10. Off-topic response is identified with is_off_topic=True and reason."""
    provider = MockProvider()
    service = ResponseIntelligenceService(provider=provider)
    comp_id = uuid4()

    question = "Describe a production incident you personally debugged."
    answer = "My favorite programming language is Python."
    competency = {"id": comp_id, "name": "Production Debugging", "description": "Troubleshooting live issues"}

    evaluation = await service.evaluate_answer(question=question, answer=answer, competency=competency)

    assert evaluation.is_off_topic is True
    assert evaluation.off_topic_reason is not None
    assert len(evaluation.off_topic_reason.strip()) > 0
    assert evaluation.demonstrated_level == 1


@pytest.mark.asyncio
async def test_on_topic_evaluation():
    """11. On-topic response evaluates with is_off_topic=False and off_topic_reason=None."""
    provider = MockProvider()
    service = ResponseIntelligenceService(provider=provider)
    comp_id = uuid4()

    question = "Describe a production incident you personally debugged."
    answer = (
        "We had a memory leak in our worker pool. I captured heap dumps using async-profiler, "
        "identified unclosed database connections in our retry middleware, patched the context manager, "
        "and verified memory stabilized under 40% threshold."
    )
    competency = {"id": comp_id, "name": "Production Debugging", "description": "Troubleshooting live issues"}

    evaluation = await service.evaluate_answer(question=question, answer=answer, competency=competency)

    assert evaluation.is_off_topic is False
    assert evaluation.off_topic_reason is None
    assert evaluation.relevance_score >= 3.0
    assert evaluation.demonstrated_level >= 3


@pytest.mark.asyncio
async def test_deterministic_mock_provider():
    """12. MockProvider returns identical deterministic evaluations for identical calls."""
    provider = MockProvider()
    comp_id = uuid4()
    question = "Explain how PostgreSQL MVCC handles row updates."
    answer = "It inserts a new tuple with updated xmin/xmax and updates the indexes."
    competency = {"id": comp_id, "name": "Databases", "description": "RDBMS internal architecture"}

    eval1 = await provider.evaluate(question=question, answer=answer, competency=competency)
    eval2 = await provider.evaluate(question=question, answer=answer, competency=competency)

    assert eval1.model_dump() == eval2.model_dump()
    assert eval1.competency_id == comp_id
    assert eval1.relevance_score == eval2.relevance_score


@pytest.mark.asyncio
async def test_service_provider_abstraction():
    """13. ResponseIntelligenceService interacts purely via the ResponseEvaluationProvider interface."""
    class CustomProvider(ResponseEvaluationProvider):
        def __init__(self):
            self.invoked = False

        async def evaluate(self, question, answer, competency, *, job_context=None):
            self.invoked = True
            return ResponseEvaluation(
                competency_id=uuid4(),
                evidence_summary="Custom evaluated evidence.",
                strengths=["Great custom provider"],
                gaps=["None"],
                relevance_score=4.0,
                depth_score=4.0,
                technical_accuracy_score=4.0,
                confidence=0.95,
                demonstrated_level=4,
                is_off_topic=False,
            )

    custom_provider = CustomProvider()
    service = ResponseIntelligenceService(provider=custom_provider)

    result = await service.evaluate_answer(
        question="What is consensus in distributed systems?",
        answer="Raft and Paxos ensure agreement across nodes.",
        competency={"id": uuid4(), "name": "Distributed Systems", "description": "Consistency algorithms"},
    )

    assert custom_provider.invoked is True
    assert result.evidence_summary == "Custom evaluated evidence."
    assert result.demonstrated_level == 4


@pytest.mark.asyncio
async def test_malformed_provider_output_rejection():
    """14. Provider returning invalid score, bad types, or missing fields is rejected."""
    mock_provider = MockProvider()
    service = ResponseIntelligenceService(provider=mock_provider)

    # Queue malformed dictionary (missing evidence_summary and invalid relevance score)
    mock_provider.queue_evaluation({
        "competency_id": uuid4(),
        "relevance_score": 999.0,  # Invalid
        "depth_score": 3.0,
    })

    with pytest.raises(ApplicationError) as exc_info:
        await service.evaluate_answer(
            question="Tell me about indexing.",
            answer="B-trees are common.",
            competency={"id": uuid4(), "name": "Databases", "description": "Index structures"},
        )
    assert exc_info.value.code == "MALFORMED_PROVIDER_OUTPUT"

    # Queue completely invalid type (e.g. integer)
    mock_provider.queue_evaluation(12345)
    with pytest.raises(ApplicationError) as exc_info_type:
        await service.evaluate_answer(
            question="Tell me about indexing.",
            answer="B-trees are common.",
            competency={"id": uuid4(), "name": "Databases", "description": "Index structures"},
        )
    assert exc_info_type.value.code == "MALFORMED_PROVIDER_OUTPUT"


# ---------------------------------------------------------------------------
# 15-17: Claude Provider Credential & Input Edge Case Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claude_provider_credential_handling():
    """15. ClaudeProvider strictly validates credentials and never exposes them."""
    # Test unconfigured provider raises ApplicationError without leaking
    provider_no_key = ClaudeProvider(api_key="")
    with pytest.raises(ApplicationError) as exc_info:
        await provider_no_key.evaluate(
            question="Question",
            answer="Answer",
            competency={"id": uuid4(), "name": "Comp", "description": "Desc"},
        )
    assert exc_info.value.code == "CLAUDE_AUTH_ERROR"

    # Test repr and str never display the API key
    secret_key = "sk-ant-secret-test-key-never-expose"
    provider_with_key = ClaudeProvider(api_key=secret_key)
    repr_str = repr(provider_with_key)
    str_val = str(provider_with_key)

    assert secret_key not in repr_str
    assert secret_key not in str_val
    assert "configured=True" in repr_str


@pytest.mark.asyncio
async def test_extremely_short_answer_not_penalized():
    """16. Extremely short answers are not automatically failed for brevity."""
    provider = MockProvider()
    service = ResponseIntelligenceService(provider=provider)
    comp_id = uuid4()

    # Short valid technical answers
    short_answer = "Kubernetes."
    result = await service.evaluate_answer(
        question="Which orchestration system did you deploy to?",
        answer=short_answer,
        competency={"id": comp_id, "name": "DevOps", "description": "Container orchestration"},
    )

    assert isinstance(result, ResponseEvaluation)
    assert result.is_off_topic is False
    assert result.relevance_score >= 3.0


@pytest.mark.asyncio
async def test_oversized_answer_handling():
    """17. Oversized answers are truncated gracefully and evaluated without crashing."""
    provider = MockProvider()
    service = ResponseIntelligenceService(provider=provider, max_answer_length=200)

    # 5000 character answer
    huge_answer = "Distributed caching prevents database overload. " * 100
    comp_id = uuid4()

    result = await service.evaluate_answer(
        question="How does caching improve scalability?",
        answer=huge_answer,
        competency={"id": comp_id, "name": "System Design", "description": "Scalability patterns"},
    )

    assert isinstance(result, ResponseEvaluation)
    # Check that mock provider received truncated answer
    assert provider.last_call is not None
    assert "[truncated for evaluation]" in provider.last_call["answer"]
    assert len(provider.last_call["answer"]) < 300


@pytest.mark.asyncio
async def test_claude_provider_mock_transport():
    """Validates ClaudeProvider with Anthropic Messages tool use format via mock HTTP transport."""
    comp_id = uuid4()

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        # Verify request headers
        assert "x-api-key" in request.headers
        assert request.headers["anthropic-version"] == "2023-06-01"

        # Mock Claude response with tool_use block
        mock_body = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_456",
                    "name": "submit_response_evaluation",
                    "input": {
                        "evidence_summary": "Candidate clearly explained Redis caching layers.",
                        "strengths": ["Clear understanding of cache invalidation"],
                        "gaps": ["Did not mention cache stampede prevention"],
                        "relevance_score": 4.5,
                        "depth_score": 4.0,
                        "technical_accuracy_score": 4.5,
                        "confidence": 0.95,
                        "demonstrated_level": 4,
                        "is_off_topic": False,
                        "off_topic_reason": None,
                    },
                }
            ],
            "stop_reason": "tool_use",
        }
        return httpx.Response(status_code=200, json=mock_body)

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as mock_client:
        provider = ClaudeProvider(api_key="test-api-key", client=mock_client)
        eval_result = await provider.evaluate(
            question="How do you handle Redis cache invalidation?",
            answer="We use write-through with short TTLs and explicit cache bus invalidation.",
            competency={"id": comp_id, "name": "Caching", "description": "Redis caching strategies"},
        )

        assert eval_result.competency_id == comp_id
        assert eval_result.relevance_score == 4.5
        assert eval_result.demonstrated_level == 4
        assert eval_result.is_off_topic is False


# ---------------------------------------------------------------------------
# 18-20: Candidate Response Persistence & Tenant Isolation Tests
# ---------------------------------------------------------------------------

async def setup_persistence_context(db):
    """Helper to set up organization, job, interview def, candidate, session, and question."""
    org = await OrganizationService.create_organization(
        db,
        name=f"Response Test Org {uuid4().hex[:8]}",
        slug=f"resp-org-{uuid4().hex[:8]}",
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
        name="Backend Evaluation",
    )
    candidate = await CandidateService.create_candidate(
        db=db,
        organization_id=org.id,
        name="Bob Candidate",
        email=f"bob-{uuid4().hex[:6]}@example.com",
    )
    competency = await CompetencyService().create_competency(
        db=db,
        organization_id=org.id,
        name="Algorithms",
        description="Algorithmic problem solving",
    )
    await CompetencyService().assign_competency_to_interview(
        db=db,
        organization_id=org.id,
        interview_definition_id=interview_def.id,
        competency_id=competency.id,
        weight=1.0,
        target_level=3,
        display_order=1,
    )
    question = await QuestionService().create_question(
        db=db,
        organization_id=org.id,
        interview_definition_id=interview_def.id,
        competency_id=competency.id,
        question_text="Explain Dijkstra's shortest path algorithm.",
        question_type=QuestionType.TECHNICAL.value,
        expected_signal="Greedy approach with priority queue and relaxation.",
        difficulty_level=3,
        display_order=1,
    )
    session = await InterviewSessionService.create_session(
        db=db,
        organization_id=org.id,
        interview_definition_id=interview_def.id,
        candidate_id=candidate.id,
    )
    await InterviewSessionService.start_session(db=db, organization_id=org.id, session_id=session.id)
    return org, session, question, competency


async def cleanup_persistence_context(db, org_ids: list[UUID]):
    """Clean up test data across organizations."""
    for org_id in org_ids:
        await db.execute(text("DELETE FROM candidate_responses WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM questions WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM interview_competencies WHERE interview_definition_id IN (SELECT id FROM interview_definitions WHERE organization_id = :org_id)"), {"org_id": org_id})
        await db.execute(text("DELETE FROM competencies WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM interview_sessions WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM candidates WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM interview_definitions WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM jobs WHERE organization_id = :org_id"), {"org_id": org_id})
        await db.execute(text("DELETE FROM organizations WHERE id = :org_id"), {"org_id": org_id})
    await db.commit()


@pytest.mark.asyncio
async def test_candidate_response_persistence():
    """18. Persist candidate response and structured evaluation in database."""
    async with AsyncSessionLocal() as db:
        org, session, question, competency = await setup_persistence_context(db)
        try:
            eval_obj = ResponseEvaluation(
                competency_id=competency.id,
                evidence_summary="Candidate clearly explained min-heap priority queue and edge relaxation.",
                strengths=["Accurate time complexity analysis", "Identified non-negative edge constraint"],
                gaps=["Did not mention Fibonacci heap variant"],
                relevance_score=4.5,
                depth_score=4.0,
                technical_accuracy_score=4.5,
                confidence=0.9,
                demonstrated_level=4,
                is_off_topic=False,
            )

            response_record = await CandidateResponseService.record_response(
                db=db,
                organization_id=org.id,
                interview_session_id=session.id,
                question_id=question.id,
                turn_number=1,
                candidate_answer="Dijkstra uses a priority queue to greedily visit closest unvisited vertices.",
                evaluation=eval_obj,
            )

            assert response_record.id is not None
            assert response_record.organization_id == org.id
            assert response_record.turn_number == 1
            assert response_record.evaluation_result is not None
            assert response_record.evaluation_result["demonstrated_level"] == 4

            # Fetch through service
            fetched = await CandidateResponseService.get_response(
                db=db,
                organization_id=org.id,
                response_id=response_record.id,
            )
            assert fetched.id == response_record.id
            assert fetched.candidate_answer == response_record.candidate_answer
        finally:
            await cleanup_persistence_context(db, [org.id])


@pytest.mark.asyncio
async def test_candidate_response_tenant_isolation():
    """19. Cross-organization response recording and retrieval is strictly prevented."""
    async with AsyncSessionLocal() as db:
        org1, session1, question1, _ = await setup_persistence_context(db)
        org2, session2, question2, _ = await setup_persistence_context(db)
        try:
            # Attempt to record response for Org 1 session using Org 2 credentials
            with pytest.raises(ApplicationError) as exc_session:
                await CandidateResponseService.record_response(
                    db=db,
                    organization_id=org2.id,
                    interview_session_id=session1.id,  # belongs to org1!
                    question_id=question2.id,
                    turn_number=1,
                    candidate_answer="Test answer",
                )
            assert exc_session.value.code == "INTERVIEW_SESSION_NOT_FOUND"

            # Attempt to record response with question from Org 1 in Org 2
            with pytest.raises(ApplicationError) as exc_question:
                await CandidateResponseService.record_response(
                    db=db,
                    organization_id=org2.id,
                    interview_session_id=session2.id,
                    question_id=question1.id,  # belongs to org1!
                    turn_number=1,
                    candidate_answer="Test answer",
                )
            assert exc_question.value.code == "QUESTION_NOT_FOUND"
        finally:
            await cleanup_persistence_context(db, [org1.id, org2.id])


@pytest.mark.asyncio
async def test_candidate_response_session_relationship():
    """20. Multi-turn responses for a session are persisted and retrieved in turn order."""
    async with AsyncSessionLocal() as db:
        org, session, question, comp = await setup_persistence_context(db)
        try:
            # Turn 1
            await CandidateResponseService.record_response(
                db=db,
                organization_id=org.id,
                interview_session_id=session.id,
                question_id=question.id,
                turn_number=1,
                candidate_answer="Turn 1 answer",
            )
            # Turn 2
            await CandidateResponseService.record_response(
                db=db,
                organization_id=org.id,
                interview_session_id=session.id,
                question_id=question.id,
                turn_number=2,
                candidate_answer="Turn 2 answer",
            )

            responses = await CandidateResponseService.get_session_responses(
                db=db,
                organization_id=org.id,
                interview_session_id=session.id,
            )

            assert len(responses) == 2
            assert responses[0].turn_number == 1
            assert responses[0].candidate_answer == "Turn 1 answer"
            assert responses[1].turn_number == 2
            assert responses[1].candidate_answer == "Turn 2 answer"
        finally:
            await cleanup_persistence_context(db, [org.id])
