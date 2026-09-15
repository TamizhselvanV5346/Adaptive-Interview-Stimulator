from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.exceptions import ApplicationError
from app.database.models.membership import OrganizationMembership
from app.database.models.organization import Organization
from app.database.models.user import User
from app.database.session import AsyncSessionLocal
from app.domain.permissions import Permission
from app.services.authorization_service import AuthorizationService


@pytest.mark.asyncio
async def test_active_member_with_permission_is_authorized():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Authorization Test Org",
            slug=f"auth-org-{uuid4().hex[:8]}",
            status="active",
        )

        user = User(
            external_id=f"user_{uuid4().hex}",
            email=f"{uuid4().hex}@example.com",
            name="Test User",
            status="active",
        )

        db.add_all([organization, user])
        await db.flush()

        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="hiring_manager",
            status="active",
        )

        db.add(membership)
        await db.commit()

        result = await AuthorizationService.authorize(
            db,
            user.id,
            organization.id,
            Permission.CREATE_INTERVIEW,
        )

        assert result.id == membership.id

        await db.delete(membership)
        await db.delete(user)
        await db.delete(organization)
        await db.commit()


@pytest.mark.asyncio
async def test_non_member_is_denied():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Access Test Org",
            slug=f"access-org-{uuid4().hex[:8]}",
            status="active",
        )

        user = User(
            external_id=f"user_{uuid4().hex}",
            email=f"{uuid4().hex}@example.com",
            name="Non Member",
            status="active",
        )

        db.add_all([organization, user])
        await db.commit()

        with pytest.raises(ApplicationError) as error:
            await AuthorizationService.authorize(
                db,
                user.id,
                organization.id,
                Permission.CREATE_INTERVIEW,
            )

        assert error.value.code == "ORGANIZATION_ACCESS_DENIED"

        await db.execute(
            delete(User).where(User.id == user.id)
        )
        await db.execute(
            delete(Organization).where(
                Organization.id == organization.id
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_member_without_permission_is_denied():
    async with AsyncSessionLocal() as db:
        organization = Organization(
            name="Reviewer Test Org",
            slug=f"review-org-{uuid4().hex[:8]}",
            status="active",
        )

        user = User(
            external_id=f"user_{uuid4().hex}",
            email=f"{uuid4().hex}@example.com",
            name="Reviewer",
            status="active",
        )

        db.add_all([organization, user])
        await db.flush()

        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="reviewer",
            status="active",
        )

        db.add(membership)
        await db.commit()

        with pytest.raises(ApplicationError) as error:
            await AuthorizationService.authorize(
                db,
                user.id,
                organization.id,
                Permission.CREATE_INTERVIEW,
            )

        assert error.value.code == "PERMISSION_DENIED"

        await db.delete(membership)
        await db.delete(user)
        await db.delete(organization)
        await db.commit()