from enum import Enum


class Permission(str, Enum):
    MANAGE_ORGANIZATION = "manage_organization"

    CREATE_JOB = "create_job"
    MANAGE_JOB = "manage_job"

    CREATE_INTERVIEW = "create_interview"
    MANAGE_INTERVIEW = "manage_interview"

    CONDUCT_INTERVIEW = "conduct_interview"

    VIEW_ASSESSMENT = "view_assessment"
    REVIEW_ASSESSMENT = "review_assessment"

    VIEW_REPORT = "view_report"
    MANAGE_USERS = "manage_users"