from tortoise import fields, models

from pantry.domain.accounts import AccountKind, AccountRole


class Account(models.Model):
    id = fields.UUIDField(primary_key=True)
    kind = fields.CharEnumField(AccountKind, default=AccountKind.HUMAN)
    email = fields.CharField(max_length=320, unique=True, null=True)
    name = fields.CharField(max_length=255, null=True)
    role = fields.CharEnumField(AccountRole, default=AccountRole.USER)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    api_keys: fields.ReverseRelation["ApiKey"]
    trolley: fields.ReverseRelation["Trolley"]

    class Meta:
        table = "accounts"


class Trolley(models.Model):
    id = fields.UUIDField(primary_key=True)
    account: fields.OneToOneRelation[Account] = fields.OneToOneField(
        "models.Account",
        related_name="trolley",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255, unique=True)
    version = fields.CharField(max_length=64, null=True)
    runtime_info = fields.JSONField(null=True)
    metrics = fields.JSONField(null=True)
    agents = fields.JSONField(default=list)
    last_seen_at = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    resource_groups: fields.ReverseRelation["ResourceGroup"]

    class Meta:
        table = "trolleys"


class ResourceGroup(models.Model):
    id = fields.UUIDField(primary_key=True)
    trolley: fields.ForeignKeyRelation[Trolley] = fields.ForeignKeyField(
        "models.Trolley",
        related_name="resource_groups",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255, unique=True)
    allocation_mode = fields.CharField(max_length=100, db_index=True)
    configuration = fields.JSONField(default=dict)
    attributes = fields.JSONField(default=dict)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    resources: fields.ReverseRelation["Resource"]

    class Meta:
        table = "resource_groups"


class Resource(models.Model):
    id = fields.UUIDField(primary_key=True)
    group: fields.ForeignKeyRelation[ResourceGroup] = fields.ForeignKeyField(
        "models.ResourceGroup",
        related_name="resources",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255)
    kind = fields.CharField(max_length=100)
    attributes = fields.JSONField(default=dict)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "resources"
        unique_together = (("group", "name"),)


class Agent(models.Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    allocation_mode = fields.CharField(max_length=100, db_index=True)
    model: fields.ForeignKeyNullableRelation["RegisteredModel"] = fields.ForeignKeyField(
        "models.RegisteredModel",
        related_name="agents",
        null=True,
        on_delete=fields.SET_NULL,
    )
    configuration = fields.JSONField(default=dict)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "agents"


class ApiKey(models.Model):
    id = fields.UUIDField(primary_key=True)
    account: fields.ForeignKeyRelation[Account] = fields.ForeignKeyField(
        "models.Account",
        related_name="api_keys",
        on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255)
    secret_hash = fields.CharField(max_length=64, unique=True)
    key_prefix = fields.CharField(max_length=20, db_index=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "api_keys"


class Credential(models.Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    secret_env = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    providers: fields.ReverseRelation["Provider"]

    class Meta:
        table = "credentials"


class Provider(models.Model):
    id = fields.UUIDField(primary_key=True)
    name = fields.CharField(max_length=255, unique=True)
    base_url = fields.CharField(max_length=2048)
    credential: fields.ForeignKeyNullableRelation[Credential] = fields.ForeignKeyField(
        "models.Credential",
        related_name="providers",
        null=True,
        on_delete=fields.SET_NULL,
    )
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    models: fields.ReverseRelation["RegisteredModel"]

    class Meta:
        table = "providers"


class RegisteredModel(models.Model):
    id = fields.UUIDField(primary_key=True)
    alias = fields.CharField(max_length=255, unique=True)
    upstream_model = fields.CharField(max_length=255)
    provider: fields.ForeignKeyRelation[Provider] = fields.ForeignKeyField(
        "models.Provider",
        related_name="models",
        on_delete=fields.RESTRICT,
    )
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    agents: fields.ReverseRelation[Agent]

    class Meta:
        table = "registered_models"
