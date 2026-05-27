from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class ProjectMemberRole(StrEnum):
    OWNER = "OWNER"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"