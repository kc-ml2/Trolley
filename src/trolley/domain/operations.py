from enum import StrEnum


class OperationAccess(StrEnum):
    ADMIN = "admin"
    RESTRICTED = "restricted"
    PUBLIC = "public"
    USER = "user"  # Legacy public access; retained for existing catalogs and clients.


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
