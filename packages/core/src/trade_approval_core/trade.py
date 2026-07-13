from collections.abc import Callable, Iterable, Iterator
from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from trade_approval_core.enums import Action, State
from trade_approval_core.errors import (
    CorruptEventLogError,
    InvalidSeqError,
    InvalidTransitionError,
    MissingTradeDetailsError,
    StrikeBeforeExecutionError,
    ValidationError,
)
from trade_approval_core.events import (
    ActionRecord,
    Approved,
    Booked,
    Cancelled,
    Event,
    SentToExecute,
    Submitted,
    Updated,
)
from trade_approval_core.trade_details import TradeDetails
from trade_approval_core.transition import (
    ApproverOnly,
    NotMaker,
    RequesterOnly,
    RequesterOrApprover,
    Transition,
    Unrestricted,
)
from trade_approval_core.types import TradeId, UserId

ALLOWED_TRANSITIONS: dict[tuple[State, Action], Transition] = {
    (State.DRAFT,                Action.SUBMIT):          Unrestricted(),
    (State.PENDING_APPROVAL,     Action.APPROVE):         NotMaker(),
    (State.NEEDS_REAPPROVAL,     Action.APPROVE):         RequesterOnly(),
    (State.PENDING_APPROVAL,     Action.UPDATE):          NotMaker(),
    (State.PENDING_APPROVAL,     Action.CANCEL):          RequesterOrApprover(),
    (State.NEEDS_REAPPROVAL,     Action.CANCEL):          RequesterOrApprover(),
    (State.APPROVED,             Action.CANCEL):          RequesterOrApprover(),
    (State.APPROVED,             Action.SEND_TO_EXECUTE): ApproverOnly(),
    (State.SENT_TO_COUNTERPARTY, Action.BOOK):            RequesterOrApprover(),
    (State.SENT_TO_COUNTERPARTY, Action.CANCEL):          RequesterOrApprover(),
}
ACTION_TO_STATE_MAP = {
    Submitted:     State.PENDING_APPROVAL,
    Approved:      State.APPROVED,
    Updated:       State.NEEDS_REAPPROVAL,
    Cancelled:     State.CANCELLED,
    SentToExecute: State.SENT_TO_COUNTERPARTY,
    Booked:        State.EXECUTED,
}

def _utc_now() -> datetime:
    return datetime.now(UTC)

class Trade:
    def __init__(self, clock: Callable[[], datetime] = _utc_now) -> None:
        self.id = TradeId(str(uuid4()))
        self._events: list[Event] = []
        self._clock = clock

    @classmethod
    def from_events(
        cls, trade_id: TradeId, events: Iterable[Event], clock: Callable[[], datetime] = _utc_now
    ) -> "Trade":
        """Rehydrate a Trade from a previously persisted event sequence.

        `events` must already be in seq order -- callers (e.g. a store reading
        rows back in seq order) own that guarantee, this just replays it.
        """
        trade = cls(clock=clock)
        trade.id = trade_id
        trade._events = list(events)
        return trade

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    @property
    def state(self) -> State:
        if not self._events:
            return State.DRAFT
        return ACTION_TO_STATE_MAP[type(self._events[-1])]

    @property
    def requester(self) -> UserId | None:
        return self._events[0].user_id if self._events else None

    @property
    def approver(self) -> UserId | None:
        for e in self._events:
            if isinstance(e, (Approved, Updated)):
                return e.user_id
        return None

    @property
    def maker(self) -> UserId | None:
        # Author of the details currently awaiting approval: the submitter, or
        # the updater once an amendment has been made. Pivots on each Update.
        for event in reversed(self._events):
            if isinstance(event, (Submitted, Updated)):
                return event.user_id
        return None

    @property
    def confirmation(self) -> str | None:
        """The counterparty's execution confirmation reference, or None before
        the trade is booked.

        Unlike the strike rate (an execution outcome folded into TradeDetails),
        the confirmation is not a trade detail - it is an execution artifact
        carried only by the Booked event, so it is surfaced here rather than on
        the details. Book is terminal, so there is at most one.
        """
        for event in self._events:
            if isinstance(event, Booked):
                return event.confirmation
        return None

    @property
    def details(self) -> TradeDetails | None:
        return self._fold(self._events)

    def details_as_of(self, seq: int) -> TradeDetails:
        if not (0 <= seq < len(self._events)):
            raise InvalidSeqError(self.id, seq)
        details = self._fold(event for event in self._events if event.seq <= seq)
        if details is None:
            raise MissingTradeDetailsError(self.id)
        return details

    def diff(self, seq_a: int, seq_b: int) -> dict[str, tuple[Any, Any]]:
        old = self.details_as_of(seq_a)
        new = self.details_as_of(seq_b)
        return {
            name: (old_value, new_value)
            for name, old_value, new_value in self._changed_fields(old, new)
        }

    def _fold(self, events: Iterable[Event]) -> TradeDetails | None:
        result: TradeDetails | None = None
        for event in events:
            if isinstance(event, Submitted):
                result = event.details
            elif isinstance(event, Updated):
                result = replace(self._require_details(result), **event.changes)
            elif isinstance(event, Booked):
                result = replace(self._require_details(result), strike_rate=event.strike_rate)
        return result

    def _require_details(self, result: TradeDetails | None) -> TradeDetails:
        if result is None:
            raise CorruptEventLogError(self.id)
        return result

    def submit(self, user: UserId, trade_details: TradeDetails) -> None:
        transition = self._lookup(self.state, Action.SUBMIT)
        transition.authorize(self, user)
        self._reject_premature_strike(trade_details)
        event = Submitted(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
            details=trade_details
        )
        self._events.append(event)

    def accept(self, user: UserId) -> None:
        transition = self._lookup(self.state, Action.APPROVE)
        transition.authorize(self, user)
        event = Approved(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
        )
        self._events.append(event)

    def cancel(self, user: UserId) -> None:
        transition = self._lookup(self.state, Action.CANCEL)
        transition.authorize(self, user)
        event = Cancelled(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
        )
        self._events.append(event)

    def send_to_execute(self, user: UserId) -> None:
        transition = self._lookup(self.state, Action.SEND_TO_EXECUTE)
        transition.authorize(self, user)
        event = SentToExecute(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
        )
        self._events.append(event)

    def book(self, user: UserId, strike_rate: Decimal, confirmation: str) -> None:
        transition = self._lookup(self.state, Action.BOOK)
        transition.authorize(self, user)
        event = Booked(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
            strike_rate=strike_rate,
            confirmation=confirmation,
        )
        self._events.append(event)

    def update(self, user: UserId, new_details: TradeDetails) -> None:
        transition = self._lookup(self.state, Action.UPDATE)
        transition.authorize(self, user)
        self._reject_premature_strike(new_details)

        details = self._retrieve_and_validate_details()
        changes = self._diff_details(details, new_details)
        if not changes:
            raise ValidationError("update must change at least one field")

        self._events.append(Updated(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
            changes=changes,
        ))

    def history(self) -> list[ActionRecord]:
        records: list[ActionRecord] = []
        state = State.DRAFT
        for event in self._events:
            before = state
            state = ACTION_TO_STATE_MAP[type(event)]
            records.append(ActionRecord(
                seq=event.seq,
                action=event.action,
                user_id=event.user_id,
                timestamp=event.timestamp,
                state_before=before,
                state_after=state,
            ))
        return records

    def _retrieve_and_validate_details(self) -> TradeDetails:
        details = self.details
        if details is None:
            raise MissingTradeDetailsError(self.id)
        return details

    @staticmethod
    def _reject_premature_strike(details: TradeDetails) -> None:
        # The strike is an execution outcome recorded by Book, not something a
        # requester or updater may supply. Enforced for both submit and update.
        if details.strike_rate is not None:
            raise StrikeBeforeExecutionError(details.strike_rate)

    @staticmethod
    def _diff_details(old: TradeDetails, new: TradeDetails) -> dict[str, Any]:
        return {
            name: new_value for name, _, new_value in Trade._changed_fields(old, new)
        }

    @staticmethod
    def _changed_fields(
        old: TradeDetails, new: TradeDetails
    ) -> Iterator[tuple[str, Any, Any]]:
        for f in fields(TradeDetails):
            old_value = getattr(old, f.name)
            new_value = getattr(new, f.name)
            if old_value != new_value:
                yield f.name, old_value, new_value

    def _lookup(self, current_state: State, action: Action) -> Transition:
        transition = ALLOWED_TRANSITIONS.get((current_state, action))
        if transition is None:
            raise InvalidTransitionError(current_state, action)
        return transition
