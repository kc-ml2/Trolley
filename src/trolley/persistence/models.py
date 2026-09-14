from tortoise import fields, models

from trolley.domain.operations import ExecutionStatus, OperationAccess
from trolley.domain.targets import TargetKind
from trolley.domain.users import UserOperationAccess, UserRole


class User(models.Model):
    id = fields.UUIDField(primary_key=True)
    email = fields.CharField(max_length=320, unique=True)
    name = fields.CharField(max_length=255)
    role = fields.CharEnumField(UserRole, default=UserRole.USER)
    operation_access = fields.CharEnumField(
        UserOperationAccess, default=UserOperationAccess.STANDARD
    )
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    api_keys: fields.ReverseRelation["ApiKey"]
    operation_grants: fields.ReverseRelation["OperationGrant"]


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
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    operations: fields.ReverseRelation["Operation"]


class TargetGrant(models.Model):
    id = fields.UUIDField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="target_grants", on_delete=fields.CASCADE
    )
    target = fields.ForeignKeyField(
        "models.Target", related_name="grants", on_delete=fields.CASCADE
    )

    class Meta:
        unique_together = (("user", "target"),)


class GroupTargetGrant(models.Model):
    id = fields.UUIDField(primary_key=True)
    group = fields.ForeignKeyField(
        "models.Group", related_name="target_grants", on_delete=fields.CASCADE
    )
    target = fields.ForeignKeyField(
        "models.Target", related_name="group_grants", on_delete=fields.CASCADE
    )

    class Meta:
        unique_together = (("group", "target"),)


class QueryExecution(models.Model):
    id = fields.UUIDField(primary_key=True)
    target = fields.ForeignKeyField("models.Target", on_delete=fields.RESTRICT)
    requested_by = fields.UUIDField()
    api_key_id = fields.UUIDField()
    sql = fields.TextField()
    status = fields.CharField(max_length=16, default="running")
    error = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    finished_at = fields.DatetimeField(null=True)


class Operation(models.Model):
    id = fields.UUIDField(primary_key=True)
    target: fields.ForeignKeyRelation[Target] = fields.ForeignKeyField(
        "models.Target", related_name="operations", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(default="")
    access = fields.CharEnumField(OperationAccess, default=OperationAccess.PUBLIC)
    input_schema = fields.JSONField(default=dict)
    definition = fields.JSONField(default=dict)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    executions: fields.ReverseRelation["Execution"]
    grants: fields.ReverseRelation["OperationGrant"]


class OperationGrant(models.Model):
    id = fields.UUIDField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="operation_grants", on_delete=fields.CASCADE
    )
    operation: fields.ForeignKeyRelation[Operation] = fields.ForeignKeyField(
        "models.Operation", related_name="grants", on_delete=fields.CASCADE
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "operation"),)


class Group(models.Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)


class GroupMembership(models.Model):
    id = fields.UUIDField(primary_key=True)
    group = fields.ForeignKeyField(
        "models.Group", related_name="memberships", on_delete=fields.CASCADE
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="memberships", on_delete=fields.CASCADE
    )

    class Meta:
        unique_together = (("group", "user"),)


class GroupOperationGrant(models.Model):
    id = fields.UUIDField(primary_key=True)
    group = fields.ForeignKeyField("models.Group", related_name="grants", on_delete=fields.CASCADE)
    operation = fields.ForeignKeyField(
        "models.Operation", related_name="group_grants", on_delete=fields.CASCADE
    )

    class Meta:
        unique_together = (("group", "operation"),)


class PageCursor(models.Model):
    id = fields.UUIDField(primary_key=True)
    operation = fields.ForeignKeyField(
        "models.Operation", related_name="page_cursors", on_delete=fields.CASCADE
    )
    user_id = fields.UUIDField()
    fingerprint = fields.CharField(max_length=64)
    offset = fields.BigIntField()
    page_size = fields.BigIntField()
    expires_at = fields.DatetimeField(db_index=True)


class ExecutionPage(models.Model):
    """Pagination context kept separately to preserve existing Execution schemas."""

    id = fields.UUIDField(primary_key=True)
    execution = fields.OneToOneField(
        "models.Execution", related_name="page", on_delete=fields.CASCADE
    )
    offset = fields.BigIntField()
    page_size = fields.BigIntField()
    input_cursor = fields.UUIDField(null=True)
    query_fingerprint = fields.CharField(max_length=64)


class ExportJob(models.Model):
    id = fields.UUIDField(primary_key=True)
    operation = fields.ForeignKeyField("models.Operation", on_delete=fields.RESTRICT)
    user_id = fields.UUIDField()
    api_key_id = fields.UUIDField()
    arguments = fields.JSONField()
    fingerprint = fields.CharField(max_length=64)
    status = fields.CharField(max_length=16, default="running")
    row_count = fields.BigIntField(default=0)
    byte_count = fields.BigIntField(default=0)
    file_bytes = fields.BigIntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField(db_index=True)
    finished_at = fields.DatetimeField(null=True)


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
