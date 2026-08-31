import asyncio
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


async def execute(
    configuration: dict,
    definition: dict,
    arguments: dict,
) -> Any:
    base_url = configuration.get("base_url", "").rstrip("/")
    path = definition.get("path", "")
    method = definition.get("method", "GET").upper()
    if not base_url or not path.startswith("/"):
        raise ValueError("An HTTP operation needs a target base_url and an absolute path")

    headers = dict(configuration.get("headers", {}))
    headers.update(definition.get("headers", {}))
    bearer_token = configuration.get("bearer_token")
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    body = None
    url = f"{base_url}{path}"
    if method in {"GET", "DELETE"}:
        if arguments:
            url = f"{url}?{urlencode(arguments)}"
    else:
        body = json.dumps(arguments).encode()
        headers.setdefault("Content-Type", "application/json")

    def send() -> Any:
        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request, timeout=configuration.get("timeout", 30)) as response:
            content = response.read()
            if not content:
                return {"status": response.status}
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"status": response.status, "body": content.decode()}

    return await asyncio.to_thread(send)
