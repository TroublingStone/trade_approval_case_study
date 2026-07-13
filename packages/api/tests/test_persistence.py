from httpx import ASGITransport, AsyncClient

from trade_approval_api.main import create_app
from trade_approval_api.settings import Settings

from .conftest import as_user


async def test_trade_survives_across_app_instances_on_the_same_db_file(tmp_path, details_payload):
    db_path = str(tmp_path / "trades.db")

    app1 = create_app(Settings(database_path=db_path))
    async with app1.router.lifespan_context(app1):
        transport1 = ASGITransport(app=app1)
        async with AsyncClient(transport=transport1, base_url="http://test") as client1:
            response = await client1.post("/trades", json=details_payload, headers=as_user("user-1"))
            trade_id = response.json()["id"]
            await client1.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

    app2 = create_app(Settings(database_path=db_path))
    async with app2.router.lifespan_context(app2):
        transport2 = ASGITransport(app=app2)
        async with AsyncClient(transport=transport2, base_url="http://test") as client2:
            response = await client2.get(f"/trades/{trade_id}")
            assert response.status_code == 200
            assert response.json()["state"] == "Approved"
            assert response.json()["details"]["notional_amount"] == "1000000"

            response = await client2.get(f"/trades/{trade_id}/history")
            assert [r["action"] for r in response.json()] == ["Submit", "Approve"]
