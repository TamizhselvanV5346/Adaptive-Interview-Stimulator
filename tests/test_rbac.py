from app.domain.permissions import Permission
from app.domain.rbac import has_permission
from app.domain.roles import Role


def test_owner_has_all_permissions():
    for permission in Permission:
        assert has_permission(Role.OWNER, permission)


def test_hiring_manager_can_manage_interviews():
    assert has_permission(
        Role.HIRING_MANAGER,
        Permission.CREATE_INTERVIEW,
    )
    assert has_permission(
        Role.HIRING_MANAGER,
        Permission.MANAGE_INTERVIEW,
    )


def test_reviewer_cannot_create_interview():
    assert not has_permission(
        Role.REVIEWER,
        Permission.CREATE_INTERVIEW,
    )


def test_reviewer_can_review_assessment():
    assert has_permission(
        Role.REVIEWER,
        Permission.REVIEW_ASSESSMENT,
    )


def test_hiring_manager_cannot_manage_users():
    assert not has_permission(
        Role.HIRING_MANAGER,
        Permission.MANAGE_USERS,
    )


def test_admin_can_manage_users():
    assert has_permission(
        Role.ADMIN,
        Permission.MANAGE_USERS,
    )