import pytest

from trolley.config import ConfigurationError, Settings, validate_runtime_settings


def test_admin_emails_parse_from_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "TROLLEY_ADMIN_EMAILS",
        " Admin@Example.com, ops@example.com ",
    )
    settings = Settings(_env_file=None)
    assert settings.admin_emails == frozenset({"admin@example.com", "ops@example.com"})


def test_email_from_is_required_when_smtp_is_configured() -> None:
    settings = Settings(
        _env_file=None,
        admin_emails=frozenset({"admin@example.com"}),
        smtp_host="smtp.example.com",
    )
    with pytest.raises(ConfigurationError, match="TROLLEY_EMAIL_FROM"):
        validate_runtime_settings(settings)


def test_runtime_settings_require_admin_email(monkeypatch) -> None:
    monkeypatch.delenv("TROLLEY_ADMIN_EMAILS", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(ConfigurationError, match="TROLLEY_ADMIN_EMAILS"):
        validate_runtime_settings(settings)
