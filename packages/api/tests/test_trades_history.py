from .conftest import as_user


class TestHistory:
    """Doc requirement #4: 'A tabular history of actions with user IDs,
    timestamps, and the state transitions.'
    """

    async def test_history_rows_have_user_ids_timestamps_and_transitions(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

        response = await client.get(f"/trades/{trade_id}/history")
        assert response.status_code == 200
        rows = response.json()
        assert [r["action"] for r in rows] == ["Submit", "Approve"]
        assert [r["seq"] for r in rows] == [0, 1]
        assert rows[0]["user_id"] == "user-1"
        assert rows[1]["user_id"] == "user-2"
        assert rows[0]["state_before"] == "Draft"
        assert rows[0]["state_after"] == "PendingApproval"
        assert rows[1]["state_before"] == "PendingApproval"
        assert rows[1]["state_after"] == "Approved"
        assert rows[0]["timestamp"] < rows[1]["timestamp"]


class TestDetailsAsOf:
    """Doc requirement #4: 'Trade details at any previous state.'"""

    async def test_details_before_an_update(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        updated_payload = {**details_payload, "notional_amount": "1200000"}
        await client.post(f"/trades/{trade_id}/update", json=updated_payload, headers=as_user("user-2"))

        response = await client.get(f"/trades/{trade_id}/details/0")
        assert response.status_code == 200
        assert response.json()["notional_amount"] == "1000000"

        response = await client.get(f"/trades/{trade_id}/details/1")
        assert response.status_code == 200
        assert response.json()["notional_amount"] == "1200000"


class TestDiff:
    """Doc requirement #4: 'Differences between two versions of trade
    details, e.g. {"notionalAmount": ("1,000,000", "1,200,000")}.'
    """

    async def test_diff_between_two_versions(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        updated_payload = {**details_payload, "notional_amount": "1200000"}
        await client.post(f"/trades/{trade_id}/update", json=updated_payload, headers=as_user("user-2"))

        response = await client.get(f"/trades/{trade_id}/diff", params={"from": 0, "to": 1})
        assert response.status_code == 200
        assert response.json() == {"notional_amount": ["1000000", "1200000"]}

    async def test_diff_of_a_version_against_itself_is_empty(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.get(f"/trades/{trade_id}/diff", params={"from": 0, "to": 0})
        assert response.status_code == 200
        assert response.json() == {}

    async def test_latest_seq_from_get_drives_diff_without_reading_history(self, client, details_payload):
        """A plain GET /trades/{id} exposes latest_seq, so a caller can diff the
        current version against the first without first walking /history.
        """
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        updated_payload = {**details_payload, "notional_amount": "1200000"}
        await client.post(f"/trades/{trade_id}/update", json=updated_payload, headers=as_user("user-2"))

        latest_seq = (await client.get(f"/trades/{trade_id}")).json()["latest_seq"]
        assert latest_seq == 1

        response = await client.get(f"/trades/{trade_id}/diff", params={"from": 0, "to": latest_seq})
        assert response.status_code == 200
        assert response.json() == {"notional_amount": ["1000000", "1200000"]}
