from .conftest import as_user


class TestNotFound:
    async def test_get_unknown_trade(self, client):
        response = await client.get("/trades/does-not-exist")
        assert response.status_code == 404

    async def test_approve_unknown_trade(self, client):
        response = await client.post("/trades/does-not-exist/approve", headers=as_user("user-1"))
        assert response.status_code == 404

    async def test_details_as_of_out_of_range_seq(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.get(f"/trades/{trade_id}/details/99")
        assert response.status_code == 404

    async def test_diff_out_of_range_seq(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.get(f"/trades/{trade_id}/diff", params={"from": 0, "to": 99})
        assert response.status_code == 404


class TestUnauthorized:
    async def test_maker_cannot_approve_own_submission(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-1"))
        assert response.status_code == 403

    async def test_non_approver_cannot_send_to_execute(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

        response = await client.post(f"/trades/{trade_id}/send-to-execute", headers=as_user("user-1"))
        assert response.status_code == 403

    async def test_outsider_cannot_cancel(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-3"))
        assert response.status_code == 403


class TestInvalidTransition:
    async def test_book_before_sent_to_counterparty(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(
            f"/trades/{trade_id}/book",
            json={"strike_rate": "1.2345", "confirmation": "CONF-1"},
            headers=as_user("user-1"),
        )
        assert response.status_code == 409

    async def test_approve_an_already_approved_trade(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))

        response = await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-1"))
        assert response.status_code == 409

    async def test_action_on_terminal_state(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-1"))

        response = await client.post(f"/trades/{trade_id}/cancel", headers=as_user("user-1"))
        assert response.status_code == 409


class TestDomainValidation:
    async def test_bad_date_order(self, client, details_payload):
        payload = {**details_payload, "trade_date": "2026-01-03", "value_date": "2026-01-02"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)

    async def test_non_positive_notional(self, client, details_payload):
        payload = {**details_payload, "notional_amount": "-100"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)

    async def test_duplicate_underlying_currency(self, client, details_payload):
        payload = {**details_payload, "underlying": ["USD", "USD"]}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422

    async def test_notional_currency_not_in_underlying(self, client, details_payload):
        payload = {**details_payload, "notional_currency": "GBP"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422

    async def test_update_with_no_changes_is_rejected(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(f"/trades/{trade_id}/update", json=details_payload, headers=as_user("user-2"))
        assert response.status_code == 422

    async def test_empty_confirmation_on_book(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]
        await client.post(f"/trades/{trade_id}/approve", headers=as_user("user-2"))
        await client.post(f"/trades/{trade_id}/send-to-execute", headers=as_user("user-2"))

        response = await client.post(
            f"/trades/{trade_id}/book",
            json={"strike_rate": "1.2345", "confirmation": "   "},
            headers=as_user("user-1"),
        )
        assert response.status_code == 422


class TestSchemaValidation:
    async def test_missing_required_field(self, client, details_payload):
        payload = {k: v for k, v in details_payload.items() if k != "counterparty"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)

    async def test_strike_rate_on_submit_is_rejected(self, client, details_payload):
        payload = {**details_payload, "strike_rate": "1.5"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422

    async def test_invalid_enum_value(self, client, details_payload):
        payload = {**details_payload, "direction": "Hold"}
        response = await client.post("/trades", json=payload, headers=as_user("user-1"))
        assert response.status_code == 422


class TestMissingUser:
    async def test_submit_without_x_user_id_header(self, client, details_payload):
        response = await client.post("/trades", json=details_payload)
        assert response.status_code == 401

    async def test_approve_without_x_user_id_header(self, client, details_payload):
        response = await client.post("/trades", json=details_payload, headers=as_user("user-1"))
        trade_id = response.json()["id"]

        response = await client.post(f"/trades/{trade_id}/approve")
        assert response.status_code == 401
