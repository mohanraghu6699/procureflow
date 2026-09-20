import pytest

from app import config
from app.config import Settings

SETTING_VARIABLES = [
    "DATABASE_URL",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "LOG_LEVEL",
    "CORS_ORIGINS",
]


def test_no_setting_has_a_default_in_code():
    """Configuration comes from the environment only: every field is required."""
    not_required = [name for name, field in Settings.model_fields.items() if not field.is_required()]
    assert not_required == []


def test_missing_variables_stop_start_up_and_are_named(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no backend/.env to fall back on
    for name in SETTING_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:very-secret-pw@db/app")

    with pytest.raises(SystemExit) as stopped:
        config.load_settings()

    message = str(stopped.value)
    for name in SETTING_VARIABLES[1:]:
        assert name in message
    assert "very-secret-pw" not in message  # names only, never values


def test_one_missing_variable_is_reported_alone(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    values = {
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET_KEY": "x",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "LOG_LEVEL": "INFO",
    }
    for name in SETTING_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(SystemExit) as stopped:
        config.load_settings()
    assert "CORS_ORIGINS" in str(stopped.value)
    assert "LOG_LEVEL" not in str(stopped.value)


def test_a_non_numeric_expiry_is_rejected_by_name(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    values = {
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET_KEY": "x",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "soon",
        "LOG_LEVEL": "INFO",
        "CORS_ORIGINS": "http://localhost:5173",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(SystemExit) as stopped:
        config.load_settings()
    assert "ACCESS_TOKEN_EXPIRE_MINUTES" in str(stopped.value)
