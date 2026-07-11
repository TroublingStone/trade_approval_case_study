from httpx import ASGITransport, AsyncClient

from trade_approval_api.main import app


async def test_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_evaluate_within_limit() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/evaluate", json={"amount": 100, "limit": 200})
    assert response.status_code == 200
    assert response.json() == {"approved": True, "reason": "within limit"}
