import itertools
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from trade_approval_core.enums import Currency, Direction
from trade_approval_core.trade_details import TradeDetails
from trade_approval_core.types import UserId


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
            strike_rate=Decimal("1.10"),
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


@pytest.fixture
def user3() -> UserId:
    return UserId("user-3")
