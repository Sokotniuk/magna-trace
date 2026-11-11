"""Synthetic test data, isolated from the production Oracle source."""

from secrets import token_urlsafe

import pytest
from fastapi.testclient import TestClient

from backend.app.main import Settings, create_app
from .synthetic import Clock, SyntheticSource


@pytest.fixture
def key():
    return token_urlsafe(32)


@pytest.fixture
def source():
    return SyntheticSource()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def app(key, source, clock):
    return create_app(Settings(api_key=key, development_routes=True), source, clock)


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def headers(key):
    return {"X-API-Key": key}


@pytest.fixture
def opened(client, headers):
    response = client.post("/api/v1/cases", json={"station_number": "SYNTHETIC-STATION"}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()
