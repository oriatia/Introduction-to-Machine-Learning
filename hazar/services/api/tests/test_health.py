import pytest
from fastapi.testclient import TestClient

from hazar_api.config import Settings
from hazar_api.main import create_app


def test_healthz() -> None:
    client = TestClient(create_app(Settings(env="test")))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_requires_secrets() -> None:
    with pytest.raises(RuntimeError):
        Settings(env="production").require_secrets()
