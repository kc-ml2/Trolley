import pytest

from trolley.config import ConfigurationError, load_settings


def test_invalid_config_does_not_echo_sensitive_values(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text("smtp:\n  password: [private-password-marker]\n")
    with pytest.raises(ConfigurationError) as caught:
        load_settings(path)
    assert "private-password-marker" not in str(caught.value)
