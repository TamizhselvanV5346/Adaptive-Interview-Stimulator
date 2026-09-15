import pytest
from sqlalchemy import text

from app.core.exceptions import ApplicationError
from app.database.session import AsyncSessionLocal
from app.services.organization_service import OrganizationService

@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback() 
        
@pytest.mark.asyncio
async def test_create_organization():
    async with AsyncSessionLocal() as db:
        organization = await OrganizationService.create_organization(
            db,
            name="Test Organization",
            slug="test-organization",
        )

        assert organization.id is not None
        assert organization.name == "Test Organization"
        assert organization.slug == "test-organization"
        assert organization.status == "active"

        await db.execute(
            text(
                "DELETE FROM organizations "
                "WHERE id = :organization_id"
            ),
            {"organization_id": str(organization.id)},
        )
        await db.commit()


@pytest.mark.asyncio
async def test_slug_is_normalized():
    async with AsyncSessionLocal() as db:
        organization = await OrganizationService.create_organization(
            db,
            name="Normalized Organization",
            slug="  NORMALIZED-ORG  ",
        )

        assert organization.slug == "normalized-org"

        await db.execute(
            text(
                "DELETE FROM organizations "
                "WHERE id = :organization_id"
            ),
            {"organization_id": str(organization.id)},
        )
        await db.commit()


@pytest.mark.asyncio
async def test_duplicate_slug_rejected():
    async with AsyncSessionLocal() as db:
        first = await OrganizationService.create_organization(
            db,
            name="First Organization",
            slug="duplicate-org",
        )

        with pytest.raises(ApplicationError) as exc_info:
            await OrganizationService.create_organization(
                db,
                name="Second Organization",
                slug="duplicate-org",
            )

        assert exc_info.value.code == "ORGANIZATION_SLUG_EXISTS"

        await db.execute(
            text(
                "DELETE FROM organizations "
                "WHERE id = :organization_id"
            ),
            {"organization_id": str(first.id)},
        )
        await db.commit()


@pytest.mark.asyncio
async def test_empty_name_rejected():
    async with AsyncSessionLocal() as db:
        with pytest.raises(ApplicationError) as exc_info:
            await OrganizationService.create_organization(
                db,
                name="   ",
                slug="valid-slug",
            )

        assert exc_info.value.code == "INVALID_ORGANIZATION_NAME"


@pytest.mark.asyncio
async def test_empty_slug_rejected():
    async with AsyncSessionLocal() as db:
        with pytest.raises(ApplicationError) as exc_info:
            await OrganizationService.create_organization(
                db,
                name="Valid Organization",
                slug="   ",
            )

        assert exc_info.value.code == "INVALID_ORGANIZATION_SLUG"