import pytest
import asyncpg
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


class MockConnection:
    """Connexion asyncpg mockée avec support du context manager asynchrone."""
    def __init__(self):
        self.fetchval = AsyncMock(return_value="00000000-0000-0000-0000-000000000001")
        self.fetchrow = AsyncMock(return_value=None)
        self.fetch = AsyncMock(return_value=[])
        self.execute = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockPool:
    """Pool asyncpg mocké."""
    def __init__(self):
        self._conn = MockConnection()

    def acquire(self):
        return self._conn

    @property
    def conn(self):
        return self._conn


@pytest.fixture
def mock_pool(monkeypatch):
    """Mock asyncpg pool pour les tests sans DB réelle."""
    pool = MockPool()

    async def fake_get_pool():
        return pool

    monkeypatch.setattr("db.client.get_pool", fake_get_pool)
    monkeypatch.setattr("pipeline.ingest.get_pool", fake_get_pool)
    return pool


@pytest.fixture
async def api_client():
    """Client HTTP pour tester l'API FastAPI."""
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
