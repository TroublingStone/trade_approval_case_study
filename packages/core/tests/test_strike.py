from decimal import Decimal

import pytest
from trade_approval_core.errors import NonFiniteStrikeRateError, StrikeBeforeExecutionError
from trade_approval_core.trade import Trade


class TestStrikeIsPostExecutionOnly:
    """Spec: 'Strike ... is only available after trades are executed.' The strike
    is never supplied by the requester or an updater -- it is recorded at Book
    time (when the counterparty confirms execution) and folded into the details.
    """

    def test_submit_rejects_a_supplied_strike(self, fake_clock, make_trade_details, user1):
        trade = Trade(clock=fake_clock)
        with pytest.raises(StrikeBeforeExecutionError):
            trade.submit(user1, make_trade_details(strike_rate=Decimal("1.10")))

    def test_update_rejects_a_supplied_strike(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        with pytest.raises(StrikeBeforeExecutionError):
            trade.update(user2, make_trade_details(strike_rate=Decimal("1.10")))

    def test_strike_is_absent_until_booked(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        assert trade.details.strike_rate is None

        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")
        assert trade.details.strike_rate == Decimal("1.30")

    @pytest.mark.parametrize("rate", [Decimal("NaN"), Decimal("Infinity")])
    def test_book_rejects_non_finite_strike(
        self, fake_clock, make_trade_details, user1, user2, rate
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        with pytest.raises(NonFiniteStrikeRateError):
            trade.book(user1, rate, confirmation="CONF-1")
        assert trade.details.strike_rate is None

    def test_diff_shows_strike_appearing_at_booking(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")

        assert trade.diff(0, 3) == {"strike_rate": (None, Decimal("1.30"))}


class TestConfirmation:
    """The execution confirmation reference is recorded by Book and exposed as
    a Trade query, so consumers can surface it without re-reading the event log.
    It is not part of TradeDetails (that only carries the strike rate).
    """

    def test_confirmation_is_none_before_booking(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        assert trade.confirmation is None

    def test_confirmation_is_available_after_booking(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")
        assert trade.confirmation == "CONF-1"
