from dataclasses import replace
from decimal import Decimal

from trade_approval_core.enums import State
from trade_approval_core.trade import Trade


class TestScenario1SubmitAndApprove:
    """Doc Example Scenario 1: a user submits a trade for approval, and it is
    approved.
    """

    def test_full_flow(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)

        trade.submit(user1, make_trade_details())
        assert trade.state == State.PENDING_APPROVAL

        trade.approve(user2)
        assert trade.state == State.APPROVED


class TestScenario2UpdateRequiringReapproval:
    """Doc Example Scenario 2: an approver updates the trade details, requiring
    reapproval from the original requester.
    """

    def test_full_flow(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)
        original = make_trade_details()

        trade.submit(user1, original)
        assert trade.state == State.PENDING_APPROVAL

        updated_details = replace(original, notional_amount=Decimal("1200000"))
        trade.update(user2, updated_details)
        assert trade.state == State.NEEDS_REAPPROVAL

        trade.approve(user1)
        assert trade.state == State.APPROVED

        # only the notional amount changed; everything else matches the
        # original submission
        assert trade.details == updated_details


class TestScenario3Execution:
    """Doc Example Scenario 3: an approved trade is sent to the counterparty
    and marked as executed.
    """

    def test_state_transitions(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)

        trade.submit(user1, make_trade_details())
        assert trade.state == State.PENDING_APPROVAL

        trade.approve(user2)
        assert trade.state == State.APPROVED

        trade.send_to_execute(user2)
        assert trade.state == State.SENT_TO_COUNTERPARTY

        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")
        assert trade.state == State.EXECUTED

    def test_details_reflect_booked_strike(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.approve(user2)
        trade.send_to_execute(user2)
        trade.book(user1, Decimal("1.30"), confirmation="CONF-1")

        assert trade.details.strike_rate == Decimal("1.30")


class TestScenario4HistoryAndDiff:
    """Doc Example Scenario 4: viewing history and differences."""

    def test_history_matches_scenario_2_steps(
        self, fake_clock, make_trade_details, user1, user2
    ):
        trade = Trade(clock=fake_clock)
        original = make_trade_details()

        trade.submit(user1, original)
        trade.update(user2, replace(original, notional_amount=Decimal("1200000")))
        trade.approve(user1)

        history = trade.history()

        assert [record.action for record in history] == ["Submit", "Update", "Approve"]
        assert [record.user_id for record in history] == [user1, user2, user1]
        assert [record.state_before for record in history] == [
            State.DRAFT,
            State.PENDING_APPROVAL,
            State.NEEDS_REAPPROVAL,
        ]
        assert [record.state_after for record in history] == [
            State.PENDING_APPROVAL,
            State.NEEDS_REAPPROVAL,
            State.APPROVED,
        ]

    def test_diff_matches_doc_example_shape(self, fake_clock, make_trade_details, user1, user2):
        trade = Trade(clock=fake_clock)
        original = make_trade_details()

        trade.submit(user1, original)
        trade.update(user2, replace(original, notional_amount=Decimal("1200000")))

        diff = trade.diff(0, 1)
        assert diff == {"notional_amount": (original.notional_amount, Decimal("1200000"))}
