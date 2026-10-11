import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import health as health_routes
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "parallel-api"}


@pytest.mark.asyncio
async def test_readiness_returns_ready_when_database_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def database_is_available() -> None:
        return None

    monkeypatch.setattr(health_routes, "check_database_connection", database_is_available)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


@pytest.mark.asyncio
async def test_readiness_returns_service_unavailable_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def database_is_unavailable() -> None:
        raise SQLAlchemyError("connection failed")

    monkeypatch.setattr(health_routes, "check_database_connection", database_is_unavailable)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
