from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.competency import Competency
from app.database.models.interview_competency import InterviewCompetency
from app.database.models.interview_definition import InterviewDefinition
from app.database.models.question import Question, QuestionType


class QuestionService:
    """Application service for question lifecycle and management."""

    @staticmethod
    async def create_question(
        db: AsyncSession,
        organization_id: UUID,
        interview_definition_id: UUID,
        question_text: str,
        question_type: str | QuestionType,
        difficulty_level: int,
        expected_signal: str,
        competency_id: UUID | None = None,
        display_order: int = 1,
        is_active: bool = True,
    ) -> Question:
        question_text = question_text.strip() if question_text else ""
        expected_signal = expected_signal.strip() if expected_signal else ""

        if not question_text:
            raise ApplicationError(
                "Question text cannot be blank",
                "INVALID_QUESTION_TEXT",
            )

        if not expected_signal:
            raise ApplicationError(
                "Expected signal cannot be blank",
                "INVALID_EXPECTED_SIGNAL",
            )

        if not 1 <= difficulty_level <= 5:
            raise ApplicationError(
                "Difficulty level must be between 1 and 5",
                "INVALID_DIFFICULTY_LEVEL",
            )

        if display_order < 1:
            raise ApplicationError(
                "Display order must be at least 1",
                "INVALID_DISPLAY_ORDER",
            )

        if isinstance(question_type, QuestionType):
            resolved_question_type = question_type.value
        elif isinstance(question_type, str):
            resolved_question_type = question_type.strip().upper()
            valid_types = {t.value for t in QuestionType}
            if resolved_question_type not in valid_types:
                raise ApplicationError(
                    f"Invalid question type '{question_type}'. Must be one of {valid_types}",
                    "INVALID_QUESTION_TYPE",
                )
        else:
            raise ApplicationError(
                "Invalid question type",
                "INVALID_QUESTION_TYPE",
            )

        # Validate interview definition belongs to organization
        interview_def = await db.scalar(
            select(InterviewDefinition).where(
                InterviewDefinition.id == interview_definition_id,
                InterviewDefinition.organization_id == organization_id,
            )
        )
        if interview_def is None:
            raise ApplicationError(
                "Interview definition was not found in this organization",
                "INTERVIEW_DEFINITION_NOT_FOUND",
            )

        # If competency is provided, validate organization scope and association to interview
        if competency_id is not None:
            competency = await db.scalar(
                select(Competency).where(
                    Competency.id == competency_id,
                    Competency.organization_id == organization_id,
                )
            )
            if competency is None:
                raise ApplicationError(
                    "Competency was not found in this organization",
                    "COMPETENCY_NOT_FOUND",
                )

            assignment = await db.scalar(
                select(InterviewCompetency).where(
                    InterviewCompetency.interview_definition_id == interview_definition_id,
                    InterviewCompetency.competency_id == competency_id,
                )
            )
            if assignment is None:
                raise ApplicationError(
                    "Competency is not assigned to this interview definition",
                    "COMPETENCY_NOT_ASSIGNED_TO_INTERVIEW",
                )

        question = Question(
            organization_id=organization_id,
            interview_definition_id=interview_definition_id,
            competency_id=competency_id,
            question_text=question_text,
            question_type=resolved_question_type,
            difficulty_level=difficulty_level,
            expected_signal=expected_signal,
            display_order=display_order,
            is_active=is_active,
        )

        db.add(question)
        await db.commit()
        await db.refresh(question)

        return question

    @staticmethod
    async def get_question(
        db: AsyncSession,
        organization_id: UUID,
        question_id: UUID,
    ) -> Question:
        question = await db.scalar(
            select(Question).where(
                Question.id == question_id,
                Question.organization_id == organization_id,
            )
        )

        if question is None:
            raise ApplicationError(
                "Question was not found in this organization",
                "QUESTION_NOT_FOUND",
            )

        return question

    @staticmethod
    async def list_questions_for_interview(
        db: AsyncSession,
        organization_id: UUID,
        interview_definition_id: UUID,
        include_inactive: bool = False,
    ) -> list[Question]:
        interview_def = await db.scalar(
            select(InterviewDefinition).where(
                InterviewDefinition.id == interview_definition_id,
                InterviewDefinition.organization_id == organization_id,
            )
        )
        if interview_def is None:
            raise ApplicationError(
                "Interview definition was not found in this organization",
                "INTERVIEW_DEFINITION_NOT_FOUND",
            )

        query = (
            select(Question)
            .where(
                Question.interview_definition_id == interview_definition_id,
                Question.organization_id == organization_id,
            )
            .order_by(Question.display_order.asc(), Question.created_at.asc())
        )

        if not include_inactive:
            query = query.where(Question.is_active.is_(True))

        result = await db.scalars(query)
        return list(result.all())

    @staticmethod
    async def deactivate_question(
        db: AsyncSession,
        organization_id: UUID,
        question_id: UUID,
    ) -> Question:
        question = await QuestionService.get_question(
            db=db,
            organization_id=organization_id,
            question_id=question_id,
        )

        question.is_active = False
        await db.commit()
        await db.refresh(question)

        return question

    @staticmethod
    async def activate_question(
        db: AsyncSession,
        organization_id: UUID,
        question_id: UUID,
    ) -> Question:
        question = await QuestionService.get_question(
            db=db,
            organization_id=organization_id,
            question_id=question_id,
        )

        question.is_active = True
        await db.commit()
        await db.refresh(question)

        return question
