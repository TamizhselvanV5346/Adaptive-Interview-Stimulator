from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.question import Question


class QuestionSelector:
    """Deterministic selection layer for interview questions."""

    @staticmethod
    async def select_next_question(
        db: AsyncSession,
        interview_definition_id: UUID,
        organization_id: UUID | None = None,
        competency_id: UUID | None = None,
        difficulty_level: int | None = None,
        used_question_ids: Iterable[UUID] | None = None,
    ) -> Question | None:
        """Select the next eligible active question based on deterministic rules.

        Selection priority:
        1. Must belong to interview_definition_id (and organization_id if provided).
        2. Must be active (is_active = True).
        3. Match requested competency if provided.
        4. Match requested difficulty if provided.
        5. Exclude already-used questions.
        6. Ordered by display_order ascending, then created_at ascending.
        7. Returns first matching Question, or None if no match.
        """
        query = select(Question).where(
            Question.interview_definition_id == interview_definition_id,
            Question.is_active.is_(True),
        )

        if organization_id is not None:
            query = query.where(Question.organization_id == organization_id)

        if competency_id is not None:
            query = query.where(Question.competency_id == competency_id)

        if difficulty_level is not None:
            query = query.where(Question.difficulty_level == difficulty_level)

        if used_question_ids:
            used_ids_list = list(used_question_ids)
            if used_ids_list:
                query = query.where(Question.id.not_in(used_ids_list))

        query = query.order_by(
            Question.display_order.asc(),
            Question.created_at.asc(),
        ).limit(1)

        result = await db.scalar(query)
        return result


async def select_next_question(
    db: AsyncSession,
    interview_definition_id: UUID,
    organization_id: UUID | None = None,
    competency_id: UUID | None = None,
    difficulty_level: int | None = None,
    used_question_ids: Iterable[UUID] | None = None,
) -> Question | None:
    """Convenience functional interface for QuestionSelector."""
    return await QuestionSelector.select_next_question(
        db=db,
        interview_definition_id=interview_definition_id,
        organization_id=organization_id,
        competency_id=competency_id,
        difficulty_level=difficulty_level,
        used_question_ids=used_question_ids,
    )
