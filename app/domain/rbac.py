from app.domain.permissions import Permission
from app.domain.roles import Role


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: set(Permission),

    Role.ADMIN: {
        Permission.MANAGE_ORGANIZATION,
        Permission.MANAGE_USERS,
        Permission.CREATE_JOB,
        Permission.MANAGE_JOB,
        Permission.CREATE_INTERVIEW,
        Permission.MANAGE_INTERVIEW,
        Permission.VIEW_ASSESSMENT,
        Permission.REVIEW_ASSESSMENT,
        Permission.VIEW_REPORT,
    },

    Role.HIRING_MANAGER: {
        Permission.CREATE_JOB,
        Permission.MANAGE_JOB,
        Permission.CREATE_INTERVIEW,
        Permission.MANAGE_INTERVIEW,
        Permission.CONDUCT_INTERVIEW,
        Permission.VIEW_ASSESSMENT,
        Permission.VIEW_REPORT,
    },

    Role.REVIEWER: {
        Permission.VIEW_ASSESSMENT,
        Permission.REVIEW_ASSESSMENT,
        Permission.VIEW_REPORT,
    },
}


def has_permission(
    role: Role,
    permission: Permission,
) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())