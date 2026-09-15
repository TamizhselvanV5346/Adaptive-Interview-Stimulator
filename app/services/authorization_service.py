from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApplicationError
from app.database.models.membership import OrganizationMembership
from app.domain.permissions import Permission
from app.domain.rbac import has_permission
from app.domain.roles import Role


class AuthorizationService:
    """Validate organization membership and permissions."""

    @staticmethod
    async def authorize(
        db: AsyncSession,
        user_id: UUID,
        organization_id: UUID,
        permission: Permission,
    ) -> OrganizationMembership:
        membership = await db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == "active",
            )
        )

        if membership is None:
            raise ApplicationError(
                "User is not an active member of this organization",
                "ORGANIZATION_ACCESS_DENIED",
            )

        try:
            role = Role(membership.role)
        except ValueError:
            raise ApplicationError(
                "Organization membership has an invalid role",
                "INVALID_ROLE",
            )

        if not has_permission(role, permission):
            raise ApplicationError(
                "User does not have permission for this operation",
                "PERMISSION_DENIED",
            )

        return membership