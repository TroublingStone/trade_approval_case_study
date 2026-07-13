from datetime import date, datetime
from decimal import Decimal

from .enums import Action, Currency, State
from .types import TradeId, UserId


class ValidationError(Exception):
    """Base class for all domain validation errors."""

class TradeError(ValidationError):
    """Base class for errors caused by violating a trading/financial domain
    rule -- e.g. date ordering, notional/underlying consistency, state
    transitions, authorization, or event-log integrity.

    Not every ValidationError is a TradeError: generic input-shape checks
    (a non-negative seq, a non-empty field) are direct ValidationError
    subclasses instead, since they'd apply to any event-sourced system and
    have nothing to do with trading specifically. TradeNotFoundError is
    deliberately excluded from both -- a missing lookup isn't invalid input.
    """


class InvalidDateOrderError(TradeError):
    """Raised when trade/value/delivery dates are not chronologically ordered."""

    def __init__(self, trade_date: date, value_date: date, delivery_date: date) -> None:
        self.trade_date = trade_date
        self.value_date = value_date
        self.delivery_date = delivery_date
        super().__init__(
            f"dates must satisfy trade <= value <= delivery "
            f"({trade_date} / {value_date} / {delivery_date})"
        )


class NonPositiveNotionalAmountError(TradeError):
    """Raised when the notional amount is not strictly positive."""

    def __init__(self, notional_amount: Decimal) -> None:
        self.notional_amount = notional_amount
        super().__init__(f"notional amount must be positive, got {notional_amount}")


class NotionalCurrencyMismatchError(TradeError):
    """Raised when the notional currency is not part of the underlying pair."""

    def __init__(self, notional_currency: Currency, underlying: tuple[Currency, Currency]) -> None:
        self.notional_currency = notional_currency
        self.underlying = underlying
        super().__init__(
            f"notional currency {notional_currency} must be part of "
            f"the underlying {underlying}"
        )


class DuplicateUnderlyingCurrencyError(TradeError):
    """Raised when both currencies in the underlying pair are the same."""

    def __init__(self, underlying: tuple[Currency, Currency]) -> None:
        self.underlying = underlying
        super().__init__(
            f"underlying currencies must be distinct, got {underlying}"
        )


class NonPositiveStrikeRateError(TradeError):
    """Raised when a strike rate is not strictly positive.

    Shared by TradeDetails.strike_rate and Booked.strike_rate -- there is one
    strike rate concept in this domain, whether validated on the folded
    details or on the event that supplies it.
    """

    def __init__(self, strike_rate: Decimal) -> None:
        self.strike_rate = strike_rate
        super().__init__(f"strike rate must be positive, got {strike_rate}")


class StrikeBeforeExecutionError(TradeError):
    """Raised when a strike rate is supplied before the trade is executed.

    Per the spec the strike (agreed rate) only exists once the counterparty
    executes the trade, so it is recorded via Book -- never provided at submit
    or update time.
    """

    def __init__(self, strike_rate: Decimal) -> None:
        self.strike_rate = strike_rate
        super().__init__(
            f"strike rate is assigned at booking and cannot be set before "
            f"execution, got {strike_rate}"
        )


class NegativeEventSeqError(ValidationError):
    """Raised when an event's seq is negative."""

    def __init__(self, seq: int) -> None:
        self.seq = seq
        super().__init__(f"event seq must be non-negative, got {seq}")


class NaiveEventTimestampError(ValidationError):
    """Raised when an event's timestamp is not timezone-aware."""

    def __init__(self, timestamp: datetime) -> None:
        self.timestamp = timestamp
        super().__init__("event timestamp must be timezone-aware (UTC)")


class EmptyChangesError(ValidationError):
    """Raised when an Updated event records no changed fields."""

    def __init__(self) -> None:
        super().__init__("Updated event must record at least one changed field")


class EmptyConfirmationError(ValidationError):
    """Raised when a Booked event's confirmation reference is empty."""

    def __init__(self) -> None:
        super().__init__("Booked event must record a non-empty confirmation reference")


class TradeNotFoundError(Exception):
    """Raised when no trade exists for a given id.

    Deliberately not a ValidationError/TradeError: a lookup miss isn't
    invalid input or a broken trading rule, so callers that catch those to
    mean "bad request" shouldn't also catch a missing trade by accident.
    """

    def __init__(self, trade_id: TradeId) -> None:
        self.trade_id = trade_id
        super().__init__(f"no trade found for id {trade_id}")


class InvalidTransitionError(TradeError):
    """Raised when an action is attempted from a state that doesn't allow it."""

    def __init__(self, state: State, action: Action) -> None:
        self.state = state
        self.action = action
        super().__init__(f"cannot {action.value} a trade in state {state}")


class MissingTradeDetailsError(TradeError):
    """Raised when a trade's details are accessed before it has been submitted."""

    def __init__(self, trade_id: TradeId) -> None:
        self.trade_id = trade_id
        super().__init__(f"trade {trade_id} has no details (not yet submitted)")


class CorruptEventLogError(TradeError):
    """Raised when Updated/Booked is folded before any Submitted event."""

    def __init__(self, trade_id: TradeId) -> None:
        self.trade_id = trade_id
        super().__init__(f"trade {trade_id} has Updated/Booked before any Submitted event")

class InvalidSeqError(TradeError):
    """Raised when a seq passed to details_as_of()/diff() has no matching event."""

    def __init__(self, trade_id: TradeId, seq: int) -> None:
        self.trade_id = trade_id
        self.seq = seq
        super().__init__(f"trade {trade_id} has no event with seq {seq}")


class ConcurrentModificationError(TradeError):
    """Raised when a store detects that a trade was persisted with more events
    than the version being saved knows about -- another writer got there first.

    Event-sourced persistence makes this an append-only primary-key conflict
    (trade_id, seq): a store implementation with genuine concurrent writers
    (e.g. SqliteTradeStore) surfaces that conflict as this error rather than
    silently overwriting or duplicating history.
    """

    def __init__(self, trade_id: TradeId) -> None:
        self.trade_id = trade_id
        super().__init__(f"trade {trade_id} was modified concurrently by another writer")


class UnauthorizedActionError(TradeError):
    """The action is valid from the current state, but this user may not do it.

    Carries the offending ``user_id`` and a short ``reason`` describing the rule
    that was violated (e.g. "must be the original requester", "approver cannot
    be the submitter (four-eyes)"). The ``reason`` is deliberately generic about
    *who* is allowed -- it names the rule, not the permitted user ids, so the
    error doesn't leak the trade's participants to an unauthorized caller.
    """

    def __init__(self, user_id: "UserId", reason: str) -> None:
        self.user_id = user_id
        self.reason = reason
        super().__init__(f"user {user_id!r} is not authorized: {reason}")
