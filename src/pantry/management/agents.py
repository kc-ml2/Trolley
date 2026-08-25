from pantry.management.validation import require_text
from pantry.models import Agent, RegisteredModel


def serialize_agent(agent: Agent) -> dict:
    return {
        "id": str(agent.id),
        "name": agent.name,
        "allocation_mode": agent.allocation_mode,
        "model_alias": agent.model.alias if agent.model else None,
        "configuration": agent.configuration,
        "is_active": agent.is_active,
    }


async def list_agents() -> list[dict]:
    agents = await Agent.all().prefetch_related("model").order_by("name")
    return [serialize_agent(agent) for agent in agents]


async def create_agent(
    name: str,
    allocation_mode: str,
    *,
    model_alias: str | None = None,
    configuration: dict | None = None,
) -> dict:
    model = None
    if model_alias is not None:
        model = await RegisteredModel.get(alias=require_text(model_alias, "model_alias"))
    agent = await Agent.create(
        name=require_text(name, "name"),
        allocation_mode=require_text(allocation_mode, "allocation_mode"),
        model=model,
        configuration=configuration or {},
    )
    return serialize_agent(agent)


async def update_agent(
    name: str,
    *,
    allocation_mode: str | None = None,
    model_alias: str | None = None,
    clear_model: bool = False,
    configuration: dict | None = None,
    is_active: bool | None = None,
) -> dict:
    if model_alias is not None and clear_model:
        raise ValueError("model_alias and clear_model cannot be used together")
    agent = await Agent.get(name=require_text(name, "name")).prefetch_related("model")
    if allocation_mode is not None:
        agent.allocation_mode = require_text(allocation_mode, "allocation_mode")
    if model_alias is not None:
        agent.model = await RegisteredModel.get(alias=require_text(model_alias, "model_alias"))
    elif clear_model:
        agent.model = None
    if configuration is not None:
        agent.configuration = configuration
    if is_active is not None:
        agent.is_active = is_active
    await agent.save()
    await agent.fetch_related("model")
    return serialize_agent(agent)
