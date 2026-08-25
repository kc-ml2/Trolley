from enum import StrEnum


class AccountKind(StrEnum):
    HUMAN = "human"
    TROLLEY = "trolley"


class AccountRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
