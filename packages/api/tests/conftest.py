import itertools
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from trade_approval_core.enums import Currency, Direction
from trade_approval_core.trade_details import TradeDetails
from trade_approval_core.types import UserId

from trade_approval_api.constants import USER_ID_HEADER
from trade_approval_api.main import create_app
from trade_approval_api.settings import Settings


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(database_path=":memory:"))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def as_user(user_id: str) -> dict[str, str]:
    return {USER_ID_HEADER: user_id}


@pytest.fixture
def details_payload() -> dict[str, Any]:
    return {
        "trading_entity": "Acme Corp",
        "counterparty": "Beta Bank",
        "direction": "Buy",
        "notional_currency": "USD",
        "notional_amount": "1000000",
        "underlying": ["USD", "EUR"],
        "trade_date": "2026-01-01",
        "value_date": "2026-01-02",
        "delivery_date": "2026-01-03",
    }


@pytest.fixture
def fake_clock() -> Callable[[], datetime]:
    counter = itertools.count()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def _clock() -> datetime:
        return start + timedelta(minutes=next(counter))

    return _clock


@pytest.fixture
def make_trade_details() -> Callable[..., TradeDetails]:
    def _factory(**overrides: object) -> TradeDetails:
        defaults = dict(
            trading_entity="Acme Corp",
            counterparty="Beta Bank",
            direction=Direction.BUY,
            notional_currency=Currency.USD,
            notional_amount=Decimal("1000000"),
            underlying=(Currency.USD, Currency.EUR),
            trade_date=date(2026, 1, 1),
            value_date=date(2026, 1, 2),
            delivery_date=date(2026, 1, 3),
        )
        defaults.update(overrides)
        return TradeDetails(**defaults)

    return _factory


@pytest.fixture
def user1() -> UserId:
    return UserId("user-1")


@pytest.fixture
def user2() -> UserId:
    return UserId("user-2")
