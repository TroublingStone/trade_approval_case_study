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


async def test_openapi_declares_error_responses(client):
    paths = (await client.get("/openapi.json")).json()["paths"]

    approve = paths["/trades/{trade_id}/approve"]["post"]["responses"]
    assert {"401", "403", "404", "409"} <= approve.keys()

    submit = paths["/trades"]["post"]["responses"]
    assert "401" in submit
    assert {"403", "409"}.isdisjoint(submit.keys())

    for read_path in ("/trades/{trade_id}", "/trades/{trade_id}/history", "/trades/{trade_id}/diff"):
        assert "404" in paths[read_path]["get"]["responses"]

    schema = approve["404"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/ErrorDetail")
