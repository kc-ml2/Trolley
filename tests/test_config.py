import pytest

from trolley.config import ConfigurationError, Settings, load_settings, validate_runtime_settings


def test_loads_settings_from_yaml(tmp_path) -> None:
    path = tmp_path / "trolley.yaml"
    path.write_text(
        """
server:
  public_base_url: https://trolley.example.com
catalog:
  database_url: sqlite:///data/trolley.db
admins:
  emails:
    - Admin@Example.com
    - ops@example.com
smtp:
  host: smtp.gmail.com
  port: 587
  security: starttls
  username: trolley@example.com
  password: app-password
  from: Trolley <trolley@example.com>
targets:
  reporting:
    kind: postgresql
    url: postgresql://reader:secret@db/reporting
""".lstrip()
    )

    settings = load_settings(path)

    assert settings.public_base_url == "https://trolley.example.com"
    assert settings.database_url == "sqlite:///data/trolley.db"
    assert settings.admin_emails == frozenset({"admin@example.com", "ops@example.com"})
    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_password.get_secret_value() == "app-password"
    assert settings.targets["reporting"]["kind"] == "postgresql"


def test_config_file_environment_variable_selects_yaml(tmp_path, monkeypatch) -> None:
    path = tmp_path / "custom.yaml"
    path.write_text("admins:\n  emails: [admin@example.com]\n")
    monkeypatch.setenv("TROLLEY_CONFIG_FILE", str(path))

    assert load_settings().admin_emails == frozenset({"admin@example.com"})


def test_email_from_is_required_when_smtp_is_configured() -> None:
    settings = Settings(
        admin_emails=frozenset({"admin@example.com"}),
        smtp_host="smtp.example.com",
    )
    with pytest.raises(ConfigurationError, match="smtp.from"):
        validate_runtime_settings(settings)


def test_runtime_settings_require_admin_email() -> None:
    with pytest.raises(ConfigurationError, match="admins.emails"):
        validate_runtime_settings(Settings())


def test_missing_config_file_is_reported(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_settings(tmp_path / "missing.yaml")
