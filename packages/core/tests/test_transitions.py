from decimal import Decimal

import pytest
from trade_approval_core.enums import Action, State
from trade_approval_core.errors import EmptyConfirmationError, InvalidTransitionError
from trade_approval_core.events import (
    Approved,
    Booked,
    Cancelled,
    SentToExecute,
    Submitted,
    Updated,
)
from trade_approval_core.trade import ALLOWED_TRANSITIONS, Trade
from trade_approval_core.transition import (
    ApproverOnly,
    NotMaker,
    RequesterOnly,
    RequesterOrApprover,
    Unrestricted,
)

ALL_STATE_ACTION_PAIRS = [(state, action) for state in State for action in Action]
INVALID_PAIRS = [pair for pair in ALL_STATE_ACTION_PAIRS if pair not in ALLOWED_TRANSITIONS]
NON_SUBMIT_VALID_TRANSITIONS = [
    (state, action, transition.target)
    for (state, action), transition in ALLOWED_TRANSITIONS.items()
    if action is not Action.SUBMIT
]


def _invoke(trade: Trade, action: Action, user, make_trade_details) -> None:
    if action is Action.SUBMIT:
        trade.submit(user, make_trade_details())
    elif action is Action.APPROVE:
        trade.accept(user)
    elif action is Action.UPDATE:
        trade.update(user, make_trade_details(counterparty="Other Bank"))
    elif action is Action.CANCEL:
        trade.cancel(user)
    elif action is Action.SEND_TO_EXECUTE:
        trade.send_to_execute(user)
    elif action is Action.BOOK:
        trade.book(user, Decimal("1.25"), confirmation="CONF-000")


@pytest.fixture
def trade_in_state(fake_clock, user1, make_trade_details):
    """Build a Trade whose state is `state`, without exercising authorization.

    This reaches into Trade._events directly and appends a single synthetic
    event of the right resulting type. Trade.state only ever looks at the
    last event's type, so this is enough to test the state machine (which
    (state, action) pairs are even allowed) independently of *who* is allowed
    to act -- that's test_authorization.py's concern, not this file's.
    """

    def _make(state: State) -> Trade:
        trade = Trade(clock=fake_clock)
        if state is State.DRAFT:
            return trade
        factories = {
            State.PENDING_APPROVAL: lambda ts: Submitted(
                seq=0, user_id=user1, timestamp=ts, details=make_trade_details()
            ),
            State.APPROVED: lambda ts: Approved(seq=0, user_id=user1, timestamp=ts),
            State.NEEDS_REAPPROVAL: lambda ts: Updated(
                seq=0, user_id=user1, timestamp=ts, changes={"counterparty": "Other Bank"}
            ),
            State.CANCELLED: lambda ts: Cancelled(seq=0, user_id=user1, timestamp=ts),
            State.SENT_TO_COUNTERPARTY: lambda ts: SentToExecute(
                seq=0, user_id=user1, timestamp=ts
            ),
            State.EXECUTED: lambda ts: Booked(
                seq=0, user_id=user1, timestamp=ts, strike_rate=Decimal("1.25"), confirmation="CONF-0"
            ),
        }
        trade._events.append(factories[state](fake_clock()))
        return trade

    return _make


def test_fresh_trade_state_is_draft(fake_clock):
    trade = Trade(clock=fake_clock)
    assert trade.state == State.DRAFT


class TestSubmit:
    def test_moves_draft_to_pending_approval(self, fake_clock, user1, make_trade_details):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        assert trade.state == State.PENDING_APPROVAL

    def test_records_correct_submitted_event(self, fake_clock, user1, make_trade_details):
        trade = Trade(clock=fake_clock)
        details = make_trade_details()

        trade.submit(user1, details)

        [event] = trade._events
        assert event.seq == 0
        assert event.user_id == user1
        assert event.details == details
        assert event.timestamp.tzinfo is not None


class TestBook:
    def test_records_strike_and_confirmation(self, fake_clock, user1, user2, make_trade_details):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.accept(user2)
        trade.send_to_execute(user2)

        trade.book(user1, Decimal("1.30"), confirmation="CONF-123")

        booked = trade._events[-1]
        assert booked.strike_rate == Decimal("1.30")
        assert booked.confirmation == "CONF-123"

    def test_confirmation_is_required(self, fake_clock, user1, user2, make_trade_details):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.accept(user2)
        trade.send_to_execute(user2)

        with pytest.raises(TypeError):
            trade.book(user1, Decimal("1.30"))

    @pytest.mark.parametrize("confirmation", ["", "   "])
    def test_empty_confirmation_is_rejected(
        self, fake_clock, user1, user2, make_trade_details, confirmation
    ):
        trade = Trade(clock=fake_clock)
        trade.submit(user1, make_trade_details())
        trade.accept(user2)
        trade.send_to_execute(user2)

        with pytest.raises(EmptyConfirmationError):
            trade.book(user1, Decimal("1.30"), confirmation=confirmation)


class TestInvalidTransitions:
    """Every (state, action) pair NOT in ALLOWED_TRANSITIONS must be rejected.
    Covers both terminal states (Executed, Cancelled x all 6 actions) and
    Draft x every action except Submit, as a byproduct of the full matrix.

    Trade._lookup() checks the (state, action) pair and raises
    InvalidTransitionError before transition.authorize() is ever called, so
    these cases never reach the authorization rules -- that's
    test_authorization.py's concern, not this file's.
    """

    @pytest.mark.parametrize(
        ("state", "action"),
        INVALID_PAIRS,
        ids=[f"{s.value}-{a.value}" for s, a in INVALID_PAIRS],
    )
    def test_rejected(self, trade_in_state, user1, make_trade_details, state, action):
        trade = trade_in_state(state)

        with pytest.raises(InvalidTransitionError) as exc_info:
            _invoke(trade, action, user1, make_trade_details)

        assert exc_info.value.state == state
        assert exc_info.value.action == action


class TestValidTransitionsBeyondSubmit:
    """Every ALLOWED_TRANSITIONS entry except Submit, verified independently of
    *who* is allowed to act -- that's test_authorization.py's job. Reusing the
    single-fabricated-user trade_in_state() here would conflate the two
    concerns now that Trade.requester/approver exist (that single user would
    end up being both requester and approver for every case, which happens to
    authorize some transitions and not others for reasons that have nothing to
    do with the state machine itself). Stubbing authorize() to a no-op keeps
    this file's scope to "is the (state, action) -> target_state table right."
    """

    @pytest.fixture(autouse=True)
    def _stub_authorize(self, monkeypatch):
        def _noop(self, trade, user):
            return None

        for cls in (
            ApproverOnly,
            NotMaker,
            RequesterOnly,
            RequesterOrApprover,
            Unrestricted,
        ):
            monkeypatch.setattr(cls, "authorize", _noop)

    @pytest.mark.parametrize(
        ("state", "action", "target_state"),
        NON_SUBMIT_VALID_TRANSITIONS,
        ids=[f"{s.value}-{a.value}" for s, a, _ in NON_SUBMIT_VALID_TRANSITIONS],
    )
    def test_succeeds(
        self, trade_in_state, user1, make_trade_details, state, action, target_state
    ):
        trade = trade_in_state(state)
        _invoke(trade, action, user1, make_trade_details)
        assert trade.state == target_state
