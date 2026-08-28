import asyncio
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


async def execute(
    configuration: dict,
    definition: dict,
    arguments: dict,
    secret_env: str | None,
) -> Any:
    base_url = configuration.get("base_url", "").rstrip("/")
    path = definition.get("path", "")
    method = definition.get("method", "GET").upper()
    if not base_url or not path.startswith("/"):
        raise ValueError("An HTTP operation needs a target base_url and an absolute path")

    headers = dict(configuration.get("headers", {}))
    headers.update(definition.get("headers", {}))
    if secret_env:
        secret = os.getenv(secret_env)
        if not secret:
            raise ValueError(f"Credential environment variable is not set: {secret_env}")
        headers["Authorization"] = f"Bearer {secret}"

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
