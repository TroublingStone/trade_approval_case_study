from decimal import Decimal

import pytest
from trade_approval_core.errors import StrikeBeforeExecutionError
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
        # user2 is not the maker, so authorization passes and we reach the
        # strike guard rather than an UnauthorizedActionError.
        with pytest.raises(StrikeBeforeExecutionError):
            trade.update(user2, make_trade_details(strike_rate=Decimal("1.10")))

    def test_strike_is_absent_until_booked(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.accept(user2)
        trade.send_to_execute(user2)
        assert trade.details.strike_rate is None

        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")
        assert trade.details.strike_rate == Decimal("1.30")

    def test_diff_shows_strike_appearing_at_booking(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())  # seq 0
        trade.accept(user2)                         # seq 1
        trade.send_to_execute(user2)                # seq 2
        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")  # seq 3

        assert trade.diff(0, 3) == {"strike_rate": (None, Decimal("1.30"))}
