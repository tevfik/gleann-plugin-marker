"""Shared test fixtures for gleann-plugin-marker."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)
