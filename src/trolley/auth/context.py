from dataclasses import dataclass

from trolley.domain.users import UserRole


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str
    api_key_id: str
    role: UserRole
