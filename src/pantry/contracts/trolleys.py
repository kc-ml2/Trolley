from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreatedTrolley:
    id: str
    account_id: str
    name: str
    api_key: str
