from enum import StrEnum


class OperationAccess(StrEnum):
    ADMIN = "admin"
    USER = "user"


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
