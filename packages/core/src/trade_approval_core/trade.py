from collections.abc import Callable
from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from trade_approval_core.enums import Action, State
from trade_approval_core.errors import (
    InvalidTransitionError,
    MissingTradeDetailsError,
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
    ApproverNotRequester,
    OriginalRequester,
    RequesterOrApprover,
    Transition,
    Unrestricted,
)
from trade_approval_core.types import TradeId, UserId

ALLOWED_TRANSITIONS: dict[tuple[State, Action], Transition] = {
    (State.DRAFT,                Action.SUBMIT):          Unrestricted(State.PENDING_APPROVAL),
    (State.PENDING_APPROVAL,     Action.APPROVE):         ApproverNotRequester(State.APPROVED),
    (State.NEEDS_REAPPROVAL,     Action.APPROVE):         OriginalRequester(State.APPROVED),
    (State.PENDING_APPROVAL,     Action.UPDATE):          ApproverNotRequester(
        State.NEEDS_REAPPROVAL
    ),
    (State.PENDING_APPROVAL,     Action.CANCEL):          RequesterOrApprover(State.CANCELLED),
    (State.NEEDS_REAPPROVAL,     Action.CANCEL):          RequesterOrApprover(State.CANCELLED),
    (State.APPROVED,             Action.CANCEL):          RequesterOrApprover(State.CANCELLED),
    (State.APPROVED,             Action.SEND_TO_EXECUTE): RequesterOrApprover(
        State.SENT_TO_COUNTERPARTY
    ),
    (State.SENT_TO_COUNTERPARTY, Action.BOOK):            RequesterOrApprover(State.EXECUTED),
    (State.SENT_TO_COUNTERPARTY, Action.CANCEL):          RequesterOrApprover(State.CANCELLED),
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
    def details(self) -> TradeDetails | None:
        result: TradeDetails | None = None
        for event in self._events:
            if isinstance(event, Submitted):
                result = event.details
            elif isinstance(event, Updated):
                result = replace(result, **event.changes)
            elif isinstance(event, Booked):
                result = replace(result, strike=event.strike)
        return result

    def submit(self, user: UserId, trade_details: TradeDetails) -> None:
        transition = self._lookup(self.state, Action.SUBMIT)
        transition.authorize(self, user)
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

    def book(self, user: UserId, strike: Decimal) -> None:
        transition = self._lookup(self.state, Action.BOOK)
        transition.authorize(self, user)
        event = Booked(
            seq=len(self._events),
            user_id=user,
            timestamp=self._clock(),
            strike=strike,
        )
        self._events.append(event)

    def update(self, user: UserId, new_details: TradeDetails) -> None:
        transition = self._lookup(self.state, Action.UPDATE)
        transition.authorize(self, user)

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
    def _diff_details(old: TradeDetails, new: TradeDetails) -> dict[str, Any]:
        return {f.name: getattr(new, f.name)
                for f in fields(TradeDetails)
                if getattr(old, f.name) != getattr(new, f.name)}

    def _lookup(self, current_state: State, action: Action) -> Transition:
        transition = ALLOWED_TRANSITIONS.get((current_state, action))
        if transition is None:
            raise InvalidTransitionError(current_state, action)
        return transition

    
        
