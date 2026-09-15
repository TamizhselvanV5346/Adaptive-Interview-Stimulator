from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    HIRING_MANAGER = "hiring_manager"
    REVIEWER = "reviewer"