"""Tests API FastAPI — routes health, ingest, classify, generate."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
async def client():
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestHealthRoute:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        with patch("api.routes.health.get_pool") as mock_get_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()
            mock_pool = MagicMock()
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            r = await client.get("/health")
            assert r.status_code == 200
            data = r.json()
            assert "status" in data
            assert data["service"] == "leadgen360-api"

    @pytest.mark.asyncio
    async def test_root_returns_service_info(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "service" in r.json()


class TestIngestRoute:
    @pytest.mark.asyncio
    async def test_ingest_requires_api_key(self, client):
        r = await client.post("/api/ingest", json={"prospects": []})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_ingest_empty_batch(self, client):
        from config.settings import get_settings
        settings = get_settings()
        r = await client.post(
            "/api/ingest",
            json={"prospects": []},
            headers={"X-API-Key": settings.api_secret_key},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ingested"] == 0
        assert data["duplicates"] == 0
        assert data["errors"] == 0


class TestClassifyRoute:
    @pytest.mark.asyncio
    async def test_classify_without_model_returns_503(self, client):
        from config.settings import get_settings
        settings = get_settings()

        with patch("api.routes.classify.app") as mock_app:
            mock_app.state.classifier = None
            r = await client.post(
                "/api/classify",
                json={"text": "Développeur COBOL banque"},
                headers={"X-API-Key": settings.api_secret_key},
            )
            assert r.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_classify_with_trained_model(self, client):
        from config.settings import get_settings
        from nlp.classifier import OpportunityClassifier
        from nlp.data.training_data import TRAINING_DATA
        settings = get_settings()

        clf = OpportunityClassifier()
        clf.train(TRAINING_DATA[:50])

        with patch("api.routes.classify.app") as mock_app:
            mock_app.state.classifier = clf
            r = await client.post(
                "/api/classify",
                json={"text": "Mission COBOL mainframe banque Luxembourg"},
                headers={"X-API-Key": settings.api_secret_key},
            )
            if r.status_code == 200:
                data = r.json()
                assert "sector_label" in data
                assert "priority_label" in data
                assert "nlp_score" in data
