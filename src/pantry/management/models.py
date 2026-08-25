from pantry.management.validation import require_text
from pantry.models import Provider, RegisteredModel


def serialize_model(registered_model: RegisteredModel) -> dict[str, str | bool]:
    return {
        "id": str(registered_model.id),
        "alias": registered_model.alias,
        "upstream_model": registered_model.upstream_model,
        "provider_name": registered_model.provider.name,
        "is_active": registered_model.is_active,
    }


async def list_models() -> list[dict[str, str | bool]]:
    models = await RegisteredModel.all().prefetch_related("provider").order_by("alias")
    return [serialize_model(model) for model in models]


async def create_model(
    alias: str, upstream_model: str, provider_name: str
) -> dict[str, str | bool]:
    provider = await Provider.get(name=require_text(provider_name, "provider_name"))
    model = await RegisteredModel.create(
        alias=require_text(alias, "alias"),
        upstream_model=require_text(upstream_model, "upstream_model"),
        provider=provider,
    )
    return serialize_model(model)


async def update_model(
    alias: str,
    *,
    upstream_model: str | None = None,
    provider_name: str | None = None,
    is_active: bool | None = None,
) -> dict[str, str | bool]:
    model = await RegisteredModel.get(alias=require_text(alias, "alias")).prefetch_related(
        "provider"
    )
    if upstream_model is not None:
        model.upstream_model = require_text(upstream_model, "upstream_model")
    if provider_name is not None:
        model.provider = await Provider.get(name=require_text(provider_name, "provider_name"))
    if is_active is not None:
        model.is_active = is_active
    await model.save()
    await model.fetch_related("provider")
    return serialize_model(model)
