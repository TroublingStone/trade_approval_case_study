async def test_openapi_json_lists_trade_endpoints(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/trades" in paths
    assert "/trades/{trade_id}" in paths
    assert "/trades/{trade_id}/approve" in paths
    assert "/trades/{trade_id}/update" in paths
    assert "/trades/{trade_id}/cancel" in paths
    assert "/trades/{trade_id}/send-to-execute" in paths
    assert "/trades/{trade_id}/book" in paths
    assert "/trades/{trade_id}/history" in paths
    assert "/trades/{trade_id}/details/{seq}" in paths
    assert "/trades/{trade_id}/diff" in paths


async def test_docs_page_is_served(client):
    response = await client.get("/docs")
    assert response.status_code == 200
