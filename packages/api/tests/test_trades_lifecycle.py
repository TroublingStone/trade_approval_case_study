from .conftest import as_user


class TestScenario1SubmitAndApprove:
    """Doc Example Scenario 1: a user submits a trade for approval, and it
    is approved.
    """

    async def test_submit_then_approve(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        assert response.status_code == 201
        body = response.json()
        assert response.headers["location"] == f"/trades/{body['id']}"
        assert body["state"] == "PendingApproval"
        assert body["requester"] == "user-1"
        assert body["approver"] is None
        assert body["details"]["notional_amount"] == "1000000"
        trade_id = body["id"]

        response = await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))
        assert response.status_code == 200
        assert response.json()["state"] == "Approved"
        assert response.json()["approver"] == "user-2"


class TestScenario2UpdateRequiresReapproval:
    """Doc Example Scenario 2: an approver updates the trade details,
    requiring reapproval from the original requester.
    """

    async def test_submit_update_then_reapprove(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        updated_payload = {**details_payload, "notional_amount": "1200000"}
        response = await client.post(
            f"/trades/{trade_id}/update", json=updated_payload, headers=as_user("user-2")
        )
        assert response.status_code == 200
        assert response.json()["state"] == "NeedsReapproval"
        assert response.json()["details"]["notional_amount"] == "1200000"
        response = await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-1"))
        assert response.status_code == 200
        assert response.json()["state"] == "Approved"


class TestScenario3Execution:
    """Doc Example Scenario 3: an approved trade is sent to the counterparty
    and marked as executed.
    """

    async def test_submit_approve_send_book(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

        response = await client.post(f"/trades/{trade_id}/send-to-execute", headers=as_user("user-2"))
        assert response.status_code == 200
        assert response.json()["state"] == "SentToCounterparty"

        response = await client.post(
            f"/trades/{trade_id}/book",
            json={"strike_rate": "1.2345", "confirmation": "CONF-1"},
            headers=as_user("user-1"),
        )
        assert response.status_code == 200
        assert response.json()["state"] == "Executed"
        assert response.json()["details"]["strike_rate"] == "1.2345"


class TestCancel:
    async def test_cancel_from_pending_approval(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-1"))
        assert response.status_code == 200
        assert response.json()["state"] == "Cancelled"

    async def test_cancel_from_approved(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

        response = await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-2"))
        assert response.status_code == 200
        assert response.json()["state"] == "Cancelled"

    async def test_cancel_from_sent_to_counterparty(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))
        await client.post(f"/trades/{trade_id}/send-to-execute", headers=as_user("user-2"))

        response = await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-1"))
        assert response.status_code == 200
        assert response.json()["state"] == "Cancelled"


class TestListAndGet:
    async def test_list_and_get_trades(self, client, details_payload):
        response_a = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        response_b = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        id_a, id_b = response_a.json()["id"], response_b.json()["id"]

        response = await client.get("/trades")
        assert response.status_code == 200
        assert {t["id"] for t in response.json()} == {id_a, id_b}

        response = await client.get(f"/trades/{id_a}")
        assert response.status_code == 200
        assert response.json()["id"] == id_a
