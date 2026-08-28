from trolley.config import Settings, get_settings


def tortoise_config(settings: Settings | None = None) -> dict:
    app_settings = settings or get_settings()
    return {
        "connections": {"default": app_settings.database_url},
        "apps": {
            "models": {
                "models": ["trolley.persistence.models"],
                "default_connection": "default",
            }
        },
        "use_tz": True,
        "timezone": "UTC",
    }
