"""Shared fixtures. Tests assert Spanish texts, so they pin LANGUAGE=es no
matter what the developer's .env says (load_env never overrides a set var)."""
import pytest


@pytest.fixture(autouse=True)
def spanish_by_default(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "es")
