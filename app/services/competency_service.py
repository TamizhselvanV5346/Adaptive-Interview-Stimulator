from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.competency import Competency
from app.database.models.interview_competency import InterviewCompetency
from app.database.models.interview_definition import InterviewDefinition


class CompetencyService:

    async def create_competency(
        self,
        db: AsyncSession,
        organization_id: UUID,
        name: str,
        description: str,
    ) -> Competency:
        name = name.strip()
        description = description.strip()

        if not name:
            raise ValueError("Competency name cannot be blank")

        if not description:
            raise ValueError("Competency description cannot be blank")

        competency = Competency(
            organization_id=organization_id,
            name=name,
            description=description,
        )

        db.add(competency)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise

        await db.refresh(competency)

        return competency

    async def get_competency(
        self,
        db: AsyncSession,
        organization_id: UUID,
        competency_id: UUID,
    ) -> Competency:
        result = await db.execute(
            select(Competency).where(
                Competency.id == competency_id,
                Competency.organization_id == organization_id,
            )
        )

        competency = result.scalar_one_or_none()

        if competency is None:
            raise ValueError("Competency not found")

        return competency

    async def assign_competency_to_interview(
        self,
        db: AsyncSession,
        organization_id: UUID,
        interview_definition_id: UUID,
        competency_id: UUID,
        weight: float = 1.0,
        target_level: int = 3,
        display_order: int = 1,
    ) -> InterviewCompetency:

        if weight <= 0:
            raise ValueError("Competency weight must be greater than zero")

        if not 1 <= target_level <= 5:
            raise ValueError("Target level must be between 1 and 5")

        if display_order < 1:
            raise ValueError("Display order must be at least 1")

        interview_result = await db.execute(
            select(InterviewDefinition).where(
                InterviewDefinition.id == interview_definition_id,
                InterviewDefinition.organization_id == organization_id,
            )
        )

        interview = interview_result.scalar_one_or_none()

        if interview is None:
            raise ValueError("Interview definition not found")

        competency_result = await db.execute(
            select(Competency).where(
                Competency.id == competency_id,
                Competency.organization_id == organization_id,
            )
        )

        competency = competency_result.scalar_one_or_none()

        if competency is None:
            raise ValueError("Competency not found")

        assignment = InterviewCompetency(
            interview_definition_id=interview_definition_id,
            competency_id=competency_id,
            weight=weight,
            target_level=target_level,
            display_order=display_order,
        )

        db.add(assignment)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise

        await db.refresh(assignment)

        return assignment

    async def list_interview_competencies(
        self,
        db: AsyncSession,
        organization_id: UUID,
        interview_definition_id: UUID,
    ) -> list[InterviewCompetency]:

        interview_result = await db.execute(
            select(InterviewDefinition).where(
                InterviewDefinition.id == interview_definition_id,
                InterviewDefinition.organization_id == organization_id,
            )
        )

        interview = interview_result.scalar_one_or_none()

        if interview is None:
            raise ValueError("Interview definition not found")

        result = await db.execute(
            select(InterviewCompetency)
            .join(
                Competency,
                Competency.id == InterviewCompetency.competency_id,
            )
            .where(
                InterviewCompetency.interview_definition_id
                == interview_definition_id,
                Competency.organization_id == organization_id,
            )
            .order_by(InterviewCompetency.display_order)
        )

        return list(result.scalars().all())