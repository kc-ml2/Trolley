from trolley.config import Settings


def test_admin_emails_parse_from_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "TROLLEY_ADMIN_EMAILS",
        " Admin@Example.com, ops@example.com ",
    )
    settings = Settings(_env_file=None)
    assert settings.admin_emails == frozenset({"admin@example.com", "ops@example.com"})
