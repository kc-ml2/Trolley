from enum import StrEnum


class OperationRequestStatus(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
