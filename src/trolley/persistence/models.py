from tortoise import fields, models

from trolley.domain.operations import ExecutionStatus, OperationAccess
from trolley.domain.targets import TargetKind
from trolley.domain.users import UserRole


class User(models.Model):
    id = fields.UUIDField(primary_key=True)
    email = fields.CharField(max_length=320, unique=True)
    name = fields.CharField(max_length=255)
    role = fields.CharEnumField(UserRole, default=UserRole.USER)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    api_keys: fields.ReverseRelation["ApiKey"]


class ApiKey(models.Model):
    id = fields.UUIDField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="api_keys", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=255)
    secret_hash = fields.CharField(max_length=64, unique=True)
    key_prefix = fields.CharField(max_length=20, db_index=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)


class Target(models.Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    kind = fields.CharEnumField(TargetKind)
    configuration = fields.JSONField(default=dict)
    secret_env = fields.CharField(max_length=255, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    operations: fields.ReverseRelation["Operation"]


class Operation(models.Model):
    id = fields.UUIDField(primary_key=True)
    target: fields.ForeignKeyRelation[Target] = fields.ForeignKeyField(
        "models.Target", related_name="operations", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(default="")
    access = fields.CharEnumField(OperationAccess, default=OperationAccess.USER)
    input_schema = fields.JSONField(default=dict)
    definition = fields.JSONField(default=dict)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    executions: fields.ReverseRelation["Execution"]


class Execution(models.Model):
    id = fields.UUIDField(primary_key=True)
    operation: fields.ForeignKeyRelation[Operation] = fields.ForeignKeyField(
        "models.Operation", related_name="executions", on_delete=fields.RESTRICT
    )
    arguments = fields.JSONField(default=dict)
    status = fields.CharEnumField(ExecutionStatus)
    result = fields.JSONField(null=True)
    error = fields.TextField(null=True)
    requested_by = fields.UUIDField(null=True)
    api_key_id = fields.UUIDField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    finished_at = fields.DatetimeField(null=True)
