from pantry.config import Settings, get_settings


def tortoise_config(settings: Settings | None = None) -> dict:
    app_settings = settings or get_settings()
    return {
        "connections": {"default": app_settings.database_url},
        "apps": {
            "models": {
                "models": ["pantry.models"],
                "default_connection": "default",
            }
        },
        "use_tz": True,
        "timezone": "UTC",
    }
