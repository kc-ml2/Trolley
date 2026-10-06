"""Master-authenticated provisioning, separate from MCP user credentials."""

import hashlib
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tortoise.transactions import in_transaction

from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email
from trolley.config import Settings
from trolley.persistence.models import Group, GroupMembership, GroupTargetGrant, Target, User


class KeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    targets: list[str] = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def email_address(cls, value: str) -> str:
        value = normalize_email(value)
        if value.count("@") != 1 or not all(value.split("@")) or any(c.isspace() for c in value):
            raise ValueError("Invalid email address")
        return value

    @field_validator("targets")
    @classmethod
    def target_names(cls, values: list[str]) -> list[str]:
        names = [value.strip() for value in values]
        if any(not name or len(name) > 255 for name in names):
            raise ValueError("Target names must contain 1 to 255 characters")
        return sorted(set(names))


async def provision(request: KeyRequest, settings: Settings) -> dict:
    if set(request.targets) - settings.targets.keys():
        raise HTTPException(404, "Target unavailable")
    async with in_transaction():
        # Consistent lock order for concurrent requests with overlapping Targets.
        targets = await (
            Target.filter(name__in=request.targets, is_active=True)
            .order_by("name")
            .select_for_update()
        )
        if len(targets) != len(request.targets):
            raise HTTPException(404, "Target unavailable")
        user, _ = await User.get_or_create(email=request.email, defaults={"name": request.email})
        user = await User.filter(id=user.id).select_for_update().get()
        if not user.is_active:
            raise HTTPException(409, "User is inactive")
        for target in targets:
            accessible = await GroupTargetGrant.filter(
                target=target, group__memberships__user=user
            ).exists()
            if not accessible:
                name = f"provisioning-target-{target.id}"
                group, _ = await Group.get_or_create(name=name)
                group = await Group.filter(id=group.id).select_for_update().get()
                # Fail closed if an operator has repurposed this managed group.
                if await GroupTargetGrant.filter(group=group).exclude(target=target).exists():
                    raise HTTPException(
                        409, "Managed group has other Targets; operator review required"
                    )
                await GroupTargetGrant.get_or_create(group=group, target=target)
                await GroupMembership.get_or_create(group=group, user=user)
        _, secret = await create_api_key(user, "provisioning")
        return {"email": user.email, "targets": request.targets, "api_key": secret}


def provisioning_router(settings: Settings) -> APIRouter:
    async def authenticate(authorization: str | None = Header(default=None)):
        configured = settings.provisioning.key
        expected = configured.get_secret_value() if configured else ""
        if not expected:
            raise HTTPException(404, "Not found")
        scheme, _, supplied = (authorization or "").partition(" ")
        # Fixed-size digests also safely handle non-ASCII header content.
        valid = secrets.compare_digest(
            hashlib.sha256(supplied.encode()).digest(), hashlib.sha256(expected.encode()).digest()
        )
        if scheme.lower() != "bearer" or not supplied or not valid:
            raise HTTPException(401, "Invalid provisioning credential")

    router = APIRouter(dependencies=[Depends(authenticate)])

    @router.post("/provision/user", status_code=201)
    async def issue_key(request: KeyRequest):
        result = await provision(request, settings)
        return JSONResponse(result, status_code=201, headers={"Cache-Control": "no-store"})

    return router
