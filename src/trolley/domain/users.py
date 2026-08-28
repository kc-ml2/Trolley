from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class UserOperationAccess(StrEnum):
    STANDARD = "standard"
    ASSIGNED_ONLY = "assigned_only"
