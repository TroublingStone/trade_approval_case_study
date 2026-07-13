from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from trade_approval_core.enums import Currency, Direction, State, Style
from trade_approval_core.errors import (
    DuplicateUnderlyingCurrencyError,
    EmptyPartyNameError,
    InvalidDateOrderError,
    NonFiniteNotionalAmountError,
    NonFiniteStrikeRateError,
    NonPositiveNotionalAmountError,
    NonPositiveStrikeRateError,
    NoOpUpdateError,
    NotionalCurrencyMismatchError,
)
from trade_approval_core.trade import Trade


class TestDateOrdering:
    def test_all_dates_equal_is_valid(self, make_trade_details):
        d = date(2026, 3, 1)
        details = make_trade_details(trade_date=d, value_date=d, delivery_date=d)
        assert details.trade_date == details.value_date == details.delivery_date == d

    @pytest.mark.parametrize(
        ("trade_date", "value_date", "delivery_date"),
        [
            (date(2026, 3, 1), date(2026, 3, 1), date(2026, 3, 5)),
            (date(2026, 3, 1), date(2026, 3, 5), date(2026, 3, 5)),
        ],
    )
    def test_partial_equalities_are_valid(
        self, make_trade_details, trade_date, value_date, delivery_date
    ):
        details = make_trade_details(
            trade_date=trade_date, value_date=value_date, delivery_date=delivery_date
        )
        assert (details.trade_date, details.value_date, details.delivery_date) == (
            trade_date,
            value_date,
            delivery_date,
        )

    def test_trade_after_value_is_rejected(self, make_trade_details):
        with pytest.raises(InvalidDateOrderError) as exc_info:
            make_trade_details(
                trade_date=date(2026, 3, 5),
                value_date=date(2026, 3, 1),
                delivery_date=date(2026, 3, 10),
            )
        assert exc_info.value.trade_date == date(2026, 3, 5)
        assert exc_info.value.value_date == date(2026, 3, 1)
        assert exc_info.value.delivery_date == date(2026, 3, 10)

    def test_value_after_delivery_is_rejected(self, make_trade_details):
        with pytest.raises(InvalidDateOrderError):
            make_trade_details(
                trade_date=date(2026, 3, 1),
                value_date=date(2026, 3, 10),
                delivery_date=date(2026, 3, 5),
            )

    def test_trade_after_delivery_is_rejected(self, make_trade_details):
        with pytest.raises(InvalidDateOrderError):
            make_trade_details(
                trade_date=date(2026, 3, 10),
                value_date=date(2026, 3, 1),
                delivery_date=date(2026, 3, 5),
            )


class TestNotionalAmount:
    def test_zero_is_rejected(self, make_trade_details):
        with pytest.raises(NonPositiveNotionalAmountError) as exc_info:
            make_trade_details(notional_amount=Decimal(0))
        assert exc_info.value.notional_amount == Decimal(0)

    def test_negative_is_rejected(self, make_trade_details):
        with pytest.raises(NonPositiveNotionalAmountError):
            make_trade_details(notional_amount=Decimal("-100"))

    def test_large_positive_is_valid(self, make_trade_details):
        details = make_trade_details(notional_amount=Decimal("1e18"))
        assert details.notional_amount == Decimal("1e18")

    @pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_non_finite_is_rejected(self, make_trade_details, amount):
        with pytest.raises(NonFiniteNotionalAmountError) as exc_info:
            make_trade_details(notional_amount=amount)
        assert not exc_info.value.notional_amount.is_finite()


class TestNotionalCurrencyMembership:
    def test_matches_first_underlying_currency_is_valid(self, make_trade_details):
        details = make_trade_details(
            notional_currency=Currency.USD, underlying=(Currency.USD, Currency.EUR)
        )
        assert details.notional_currency == Currency.USD

    def test_matches_second_underlying_currency_is_valid(self, make_trade_details):
        details = make_trade_details(
            notional_currency=Currency.EUR, underlying=(Currency.USD, Currency.EUR)
        )
        assert details.notional_currency == Currency.EUR

    def test_not_in_underlying_is_rejected(self, make_trade_details):
        with pytest.raises(NotionalCurrencyMismatchError) as exc_info:
            make_trade_details(
                notional_currency=Currency.GBP, underlying=(Currency.USD, Currency.EUR)
            )
        assert exc_info.value.notional_currency == Currency.GBP
        assert exc_info.value.underlying == (Currency.USD, Currency.EUR)


class TestUnderlyingCurrencyPair:
    """An FX forward's underlying must be two distinct currencies -- a
    same-currency pair has no meaningful exchange rate.
    """

    def test_duplicate_currency_pair_is_rejected(self, make_trade_details):
        with pytest.raises(DuplicateUnderlyingCurrencyError) as exc_info:
            make_trade_details(
                notional_currency=Currency.USD, underlying=(Currency.USD, Currency.USD)
            )
        assert exc_info.value.underlying == (Currency.USD, Currency.USD)

    def test_distinct_pair_is_valid_regardless_of_order(self, make_trade_details):
        make_trade_details(
            notional_currency=Currency.USD, underlying=(Currency.USD, Currency.EUR)
        )
        make_trade_details(
            notional_currency=Currency.USD, underlying=(Currency.EUR, Currency.USD)
        )


class TestStrikeRate:
    def test_unset_strike_is_valid(self, make_trade_details):
        assert make_trade_details().strike_rate is None

    def test_positive_strike_is_valid(self, make_trade_details):
        assert make_trade_details(strike_rate=Decimal("1.10")).strike_rate == Decimal("1.10")

    def test_zero_is_rejected(self, make_trade_details):
        with pytest.raises(NonPositiveStrikeRateError) as exc_info:
            make_trade_details(strike_rate=Decimal(0))
        assert exc_info.value.strike_rate == Decimal(0)

    def test_negative_is_rejected(self, make_trade_details):
        with pytest.raises(NonPositiveStrikeRateError):
            make_trade_details(strike_rate=Decimal("-1.5"))

    @pytest.mark.parametrize("rate", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    def test_non_finite_is_rejected(self, make_trade_details, rate):
        with pytest.raises(NonFiniteStrikeRateError):
            make_trade_details(strike_rate=rate)


def test_first_failing_check_wins(make_trade_details):
    with pytest.raises(InvalidDateOrderError):
        make_trade_details(
            trade_date=date(2026, 3, 5),
            value_date=date(2026, 3, 1),
            delivery_date=date(2026, 3, 1),
            notional_amount=Decimal(0),
        )


@pytest.mark.parametrize(
    "code",
    [
        "XXX",
        "XTS",
        "XAU",
        "CLF",
        "XDR",
        "ZWL",
    ],
)
def test_non_currency_code_rejected_by_enum(code):
    with pytest.raises(ValueError):
        Currency(code)


class TestPartyNames:
    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_blank_trading_entity_is_rejected(self, make_trade_details, value):
        with pytest.raises(EmptyPartyNameError) as exc_info:
            make_trade_details(trading_entity=value)
        assert exc_info.value.field == "trading_entity"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_counterparty_is_rejected(self, make_trade_details, value):
        with pytest.raises(EmptyPartyNameError) as exc_info:
            make_trade_details(counterparty=value)
        assert exc_info.value.field == "counterparty"


class TestNoOpUpdate:
    def test_update_with_identical_details_is_rejected(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        details = make_trade_details()
        trade.submit(user1, details)
        with pytest.raises(NoOpUpdateError):
            trade.update(user2, replace(details))
        assert trade.state == State.PENDING_APPROVAL
        assert len(trade.events) == 1

    def test_update_differing_only_in_decimal_precision_is_a_no_op(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details(notional_amount=Decimal("1000000")))
        with pytest.raises(NoOpUpdateError):
            trade.update(
                user2, make_trade_details(notional_amount=Decimal("1000000.00"))
            )


class TestDirectionAndStyle:
    def test_buy_and_sell_are_both_valid(self, make_trade_details):
        assert make_trade_details(direction=Direction.BUY).direction == Direction.BUY
        assert make_trade_details(direction=Direction.SELL).direction == Direction.SELL

    def test_style_defaults_to_forward(self, make_trade_details):
        assert make_trade_details().style == Style.FORWARD
