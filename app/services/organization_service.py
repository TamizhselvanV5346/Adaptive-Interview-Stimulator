from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.organization import Organization


class OrganizationService:
    """Application service for organization lifecycle operations."""

    @staticmethod
    async def create_organization(
        db: AsyncSession,
        name: str,
        slug: str,
    ) -> Organization:
        name = name.strip()
        slug = slug.strip().lower()

        if not name:
            raise ApplicationError(
                "Organization name cannot be empty",
                "INVALID_ORGANIZATION_NAME",
            )

        if not slug:
            raise ApplicationError(
                "Organization slug cannot be empty",
                "INVALID_ORGANIZATION_SLUG",
            )

        existing = await db.scalar(
            select(Organization).where(Organization.slug == slug)
        )

        if existing is not None:
            raise ApplicationError(
                f"Organization slug '{slug}' already exists",
                "ORGANIZATION_SLUG_EXISTS",
            )

        organization = Organization(
            name=name,
            slug=slug,
            status="active",
        )

        db.add(organization)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise ApplicationError(
                f"Organization slug '{slug}' already exists",
                "ORGANIZATION_SLUG_EXISTS",
            )

        await db.refresh(organization)

        return organization

    @staticmethod
    async def get_organization(
        db: AsyncSession,
        organization_id: UUID,
    ) -> Organization:
        organization = await db.scalar(
            select(Organization).where(
                Organization.id == organization_id
            )
        )

        if organization is None:
            raise ApplicationError(
                "Organization was not found",
                "ORGANIZATION_NOT_FOUND",
            )

        return organization