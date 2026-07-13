from decimal import Decimal

import pytest
from trade_approval_core.enums import State
from trade_approval_core.errors import InvalidSeqError
from trade_approval_core.trade import Trade


class TestHistory:
    def test_single_submit_event(self, fake_clock, make_trade_details, user1):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        [record] = trade.history()
        assert record.seq == 0
        assert record.action == "Submit"
        assert record.user_id == user1
        assert record.timestamp.tzinfo is not None
        assert record.state_before == State.DRAFT
        assert record.state_after == State.PENDING_APPROVAL

    def test_multi_event_trade_in_seq_order(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)

        history = trade.history()

        assert [record.seq for record in history] == [0, 1, 2]
        assert [record.action for record in history] == ["Submit", "Approve", "SendToExecute"]
        assert [record.state_before for record in history] == [
            State.DRAFT,
            State.PENDING_APPROVAL,
            State.APPROVED,
        ]
        assert [record.state_after for record in history] == [
            State.PENDING_APPROVAL,
            State.APPROVED,
            State.SENT_TO_COUNTERPARTY,
        ]
        timestamps = [record.timestamp for record in history]
        assert timestamps == sorted(timestamps)

    def test_terminal_event_state_after_matches_trade_state(
        self, fake_clock, make_trade_details, user1
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.cancel(user1)

        history = trade.history()
        assert history[-1].state_after == State.CANCELLED == trade.state


class TestDetailsAtPreviousState:
    """Doc requirement #4: 'trade details at any previous state,' exposed via
    Trade.details_as_of(seq).
    """

    def test_details_before_an_update(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)
        original = make_trade_details()
        trade.submit(user1, original)
        trade.update(user2, make_trade_details(notional_amount=Decimal("1200000")))

        assert trade.details_as_of(0) == original

    def test_details_after_a_book_folds_in_the_strike(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")

        assert trade.details_as_of(3).strike_rate == Decimal("1.30")


class TestInvalidSeq:
    """details_as_of()/diff() take a caller-supplied seq -- e.g. from an API
    request for "trade details at previous state N." An out-of-range value is
    a normal input to guard against, not just an internal invariant.
    """

    def test_negative_seq_is_rejected(self, fake_clock, make_trade_details, user1):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        with pytest.raises(InvalidSeqError) as exc_info:
            trade.details_as_of(-1)
        assert exc_info.value.trade_id == trade.id
        assert exc_info.value.seq == -1

    def test_seq_past_last_event_is_rejected(self, fake_clock, make_trade_details, user1):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        with pytest.raises(InvalidSeqError) as exc_info:
            trade.details_as_of(1)
        assert exc_info.value.seq == 1

    def test_diff_propagates_invalid_seq(self, fake_clock, make_trade_details, user1):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        with pytest.raises(InvalidSeqError):
            trade.diff(0, 5)


class TestDiff:
    """Doc requirement #4: 'differences between two versions of trade details,'
    e.g. {"notionalAmount": ("1,000,000", "1,200,000")}, exposed via Trade.diff().
    """

    def test_diff_between_two_versions_returns_old_and_new(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        original = make_trade_details()
        trade.submit(user1, original)
        trade.update(user2, make_trade_details(notional_amount=Decimal("1200000")))

        diff = trade.diff(0, 1)
        assert diff == {"notional_amount": (original.notional_amount, Decimal("1200000"))}

    def test_diff_of_a_version_against_itself_is_empty(
        self, fake_clock, make_trade_details, user1
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())

        assert trade.diff(0, 0) == {}
