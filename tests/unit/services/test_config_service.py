"""Tests for environment-sensitive application configuration."""

from app.services.config_service import ConfigService


def test_database_url_environment_override(monkeypatch) -> None:
    expected = "postgresql+psycopg://runtime_user:runtime_password@db:5432/runtime"
    monkeypatch.setenv("OUTBOX_DATABASE_URL", expected)

    assert ConfigService("test").get_database_url() == expected


def test_database_url_uses_environment_file_when_override_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("OUTBOX_DATABASE_URL", raising=False)

    assert ConfigService("test").get_database_url().endswith("@localhost:5432/outbox")
