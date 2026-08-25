from pantry.models import Agent, ResourceGroup, Trolley
from pantry.services.credential_resolver import resolve_credential


async def build_trolley_configuration(trolley: Trolley) -> dict:
    groups = (
        await ResourceGroup.filter(trolley=trolley, is_active=True)
        .order_by("name")
        .prefetch_related("resources")
    )
    allocation_modes = {group.allocation_mode for group in groups}
    agents = (
        await Agent.filter(
            allocation_mode__in=allocation_modes,
            is_active=True,
        ).prefetch_related("model", "model__provider", "model__provider__credential")
        if allocation_modes
        else []
    )
    agents_by_mode: dict[str, list[Agent]] = {}
    for agent in sorted(agents, key=lambda item: item.name):
        agents_by_mode.setdefault(agent.allocation_mode, []).append(agent)

    providers: dict[str, dict] = {}
    resource_groups: list[dict] = []
    for group in groups:
        group_agents: dict[str, dict] = {}
        for agent in agents_by_mode.get(group.allocation_mode, []):
            agent_config = {"configuration": agent.configuration}
            model = agent.model
            if model is not None:
                if not model.is_active or not model.provider.is_active:
                    raise ValueError(f"Unavailable model: {model.alias}")
                provider = model.provider
                credential = resolve_credential(provider.credential)
                if credential.status not in {"configured", "not_configured"}:
                    raise ValueError(f"Provider credential is {credential.status}: {provider.name}")
                providers[provider.name] = {
                    "base_url": provider.base_url,
                    "api_key": (
                        credential.authorization.removeprefix("Bearer ")
                        if credential.authorization
                        else None
                    ),
                }
                agent_config["model"] = {
                    "alias": model.alias,
                    "upstream_model": model.upstream_model,
                    "provider": provider.name,
                }
            group_agents[agent.name] = agent_config

        resource_groups.append(
            {
                "id": str(group.id),
                "name": group.name,
                "allocation_mode": group.allocation_mode,
                "configuration": group.configuration,
                "attributes": group.attributes,
                "resources": [
                    {
                        "id": str(resource.id),
                        "name": resource.name,
                        "kind": resource.kind,
                        "attributes": resource.attributes,
                    }
                    for resource in sorted(group.resources, key=lambda item: item.name)
                    if resource.is_active
                ],
                "agents": group_agents,
            }
        )

    return {
        "type": "configuration",
        "providers": providers,
        "resource_groups": resource_groups,
    }
