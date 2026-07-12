from decimal import Decimal

import pytest
from trade_approval_core.enums import State
from trade_approval_core.events import Approved, SentToExecute, Submitted, Updated
from trade_approval_core.trade import Trade


@pytest.fixture
def build_trade(fake_clock):
    """Build a Trade's event log directly from (event_class, user, extra_kwargs)
    steps, bypassing authorize(). Trade.requester/approver only look at event
    history, so this still gives correct role attribution -- it's just faster
    and more explicit than going through the real action methods for setup.
    """

    def _build(*steps):
        trade = Trade(clock=fake_clock)
        for seq, (event_cls, user, extra) in enumerate(steps):
            trade._events.append(
                event_cls(seq=seq, user_id=user, timestamp=fake_clock(), **extra)
            )
        return trade

    return _build


def _unauthorized():
    from trade_approval_core.errors import UnauthorizedActionError

    return pytest.raises(UnauthorizedActionError)


class TestApproveFromPendingApproval:
    """(PendingApproval, Approve) uses ApproverNotRequester: anyone except the
    original requester may approve -- there's no pre-assigned approver yet.
    """

    def test_original_requester_cannot_approve_own_trade(
        self, build_trade, make_trade_details, user1
    ):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        with _unauthorized():
            trade.accept(user1)

    def test_any_other_user_can_approve(self, build_trade, make_trade_details, user1, user3):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        trade.accept(user3)
        assert trade.state == State.APPROVED


class TestUpdateFromPendingApproval:
    """(PendingApproval, Update) also uses ApproverNotRequester."""

    def test_original_requester_cannot_update_own_trade(
        self, build_trade, make_trade_details, user1
    ):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        with _unauthorized():
            trade.update(user1, make_trade_details(counterparty="Other Bank"))

    def test_any_other_user_can_update(self, build_trade, make_trade_details, user1, user3):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        trade.update(user3, make_trade_details(counterparty="Other Bank"))
        assert trade.state == State.NEEDS_REAPPROVAL


class TestReapproval:
    """(NeedsReapproval, Approve) uses OriginalRequester: only the user who
    originally submitted may reapprove -- not just "not the requester".
    """

    def test_original_requester_can_reapprove(
        self, build_trade, make_trade_details, user1, user2
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Updated, user2, {"changes": {"counterparty": "Other Bank"}}),
        )
        trade.accept(user1)
        assert trade.state == State.APPROVED

    def test_the_updater_cannot_reapprove_their_own_update(
        self, build_trade, make_trade_details, user1, user2
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Updated, user2, {"changes": {"counterparty": "Other Bank"}}),
        )
        with _unauthorized():
            trade.accept(user2)

    def test_unrelated_third_party_cannot_reapprove(
        self, build_trade, make_trade_details, user1, user2, user3
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Updated, user2, {"changes": {"counterparty": "Other Bank"}}),
        )
        with _unauthorized():
            trade.accept(user3)


class TestCancel:
    """(*, Cancel) uses RequesterOrApprover from every non-Draft, non-terminal
    state. Before anyone has approved/updated, only the requester qualifies --
    there's no approver identity yet.
    """

    def test_requester_can_cancel_from_pending_approval(
        self, build_trade, make_trade_details, user1
    ):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        trade.cancel(user1)
        assert trade.state == State.CANCELLED

    def test_unrelated_user_cannot_cancel_before_anyone_has_approved(
        self, build_trade, make_trade_details, user1, user2
    ):
        trade = build_trade((Submitted, user1, {"details": make_trade_details()}))
        with _unauthorized():
            trade.cancel(user2)

    @pytest.mark.parametrize("actor", ["requester", "approver"])
    def test_requester_or_approver_can_cancel_from_approved(
        self, build_trade, make_trade_details, user1, user2, actor
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
        )
        trade.cancel(user1 if actor == "requester" else user2)
        assert trade.state == State.CANCELLED

    def test_unrelated_third_party_cannot_cancel_from_approved(
        self, build_trade, make_trade_details, user1, user2, user3
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
        )
        with _unauthorized():
            trade.cancel(user3)

    def test_unrelated_third_party_cannot_cancel_from_sent_to_counterparty(
        self, build_trade, make_trade_details, user1, user2, user3
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
            (SentToExecute, user2, {}),
        )
        with _unauthorized():
            trade.cancel(user3)


class TestBook:
    """(SentToCounterparty, Book) uses RequesterOrApprover per the doc."""

    @pytest.mark.parametrize("actor", ["requester", "approver"])
    def test_requester_or_approver_can_book(
        self, build_trade, make_trade_details, user1, user2, actor
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
            (SentToExecute, user2, {}),
        )
        trade.book(user1 if actor == "requester" else user2, Decimal("1.25"))
        assert trade.state == State.EXECUTED

    def test_unrelated_third_party_cannot_book(
        self, build_trade, make_trade_details, user1, user2, user3
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
            (SentToExecute, user2, {}),
        )
        with _unauthorized():
            trade.book(user3, Decimal("1.25"))


class TestSendToExecute:
    """(Approved, SendToExecute): per plan finding #5, the doc says this
    should be approver-only, not RequesterOrApprover as currently coded --
    these tests assert the *intended* (doc-correct) behavior.
    test_requester_cannot_send_to_execute will fail until ALLOWED_TRANSITIONS'
    SendToExecute entry is switched to an approver-only transition.
    """

    def test_approver_can_send_to_execute(
        self, build_trade, make_trade_details, user1, user2
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
        )
        trade.send_to_execute(user2)
        assert trade.state == State.SENT_TO_COUNTERPARTY

    def test_requester_cannot_send_to_execute(
        self, build_trade, make_trade_details, user1, user2
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
        )
        with _unauthorized():
            trade.send_to_execute(user1)

    def test_unrelated_third_party_cannot_send_to_execute(
        self, build_trade, make_trade_details, user1, user2, user3
    ):
        trade = build_trade(
            (Submitted, user1, {"details": make_trade_details()}),
            (Approved, user2, {}),
        )
        with _unauthorized():
            trade.send_to_execute(user3)
