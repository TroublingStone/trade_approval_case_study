from datetime import date, datetime
from decimal import Decimal

from .enums import Action, Currency, State
from .types import TradeId, UserId


class TradeError(Exception):
    """Base class for every domain rejection in this library.

    Catching TradeError means "the request was refused for a domain reason":
    unacceptable input values (ValidationError), an action not allowed from
    the current state (InvalidTransitionError), a user who may not act
    (UnauthorizedActionError), a lost write race (ConcurrentModificationError),
    or event-log integrity problems (CorruptEventLogError and friends).

    TradeNotFoundError is deliberately excluded -- a lookup miss is not a
    domain rejection.
    """

class ValidationError(TradeError):
    """Base class for value-validation failures: the supplied details or
    event fields are unacceptable regardless of the trade's state -- date
    ordering, notional/strike bounds, party names, currency consistency,
    event shape (seq, timestamp, changes, confirmation).

    The non-value rejections -- state transitions, authorization,
    concurrency, log integrity -- are sibling TradeError subclasses, so
    catching ValidationError never swallows a state conflict or a
    permissions failure.
    """


class InvalidDateOrderError(ValidationError):
    """Raised when trade/value/delivery dates are not chronologically ordered."""

    def __init__(self, trade_date: date, value_date: date, delivery_date: date) -> None:
        self.trade_date = trade_date
        self.value_date = value_date
        self.delivery_date = delivery_date
        super().__init__(
            f"dates must satisfy trade <= value <= delivery "
            f"({trade_date} / {value_date} / {delivery_date})"
        )


class NonPositiveNotionalAmountError(ValidationError):
    """Raised when the notional amount is not strictly positive."""

    def __init__(self, notional_amount: Decimal) -> None:
        self.notional_amount = notional_amount
        super().__init__(f"notional amount must be positive, got {notional_amount}")


class NonFiniteNotionalAmountError(ValidationError):
    """Raised when the notional amount is NaN or infinite.

    Checked before the sign check: comparing a NaN Decimal signals
    decimal.InvalidOperation, which would otherwise escape the domain error
    hierarchy entirely.
    """

    def __init__(self, notional_amount: Decimal) -> None:
        self.notional_amount = notional_amount
        super().__init__(f"notional amount must be a finite number, got {notional_amount}")


class EmptyPartyNameError(ValidationError):
    """Raised when the trading entity or counterparty name is empty or blank."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"{field} must be a non-empty string")


class NotionalCurrencyMismatchError(ValidationError):
    """Raised when the notional currency is not part of the underlying pair."""

    def __init__(self, notional_currency: Currency, underlying: tuple[Currency, Currency]) -> None:
        self.notional_currency = notional_currency
        self.underlying = underlying
        super().__init__(
            f"notional currency {notional_currency} must be part of "
            f"the underlying {underlying}"
        )


class DuplicateUnderlyingCurrencyError(ValidationError):
    """Raised when both currencies in the underlying pair are the same."""

    def __init__(self, underlying: tuple[Currency, Currency]) -> None:
        self.underlying = underlying
        super().__init__(
            f"underlying currencies must be distinct, got {underlying}"
        )


class NonPositiveStrikeRateError(ValidationError):
    """Raised when a strike rate is not strictly positive.

    Shared by TradeDetails.strike_rate and Booked.strike_rate -- there is one
    strike rate concept in this domain, whether validated on the folded
    details or on the event that supplies it.
    """

    def __init__(self, strike_rate: Decimal) -> None:
        self.strike_rate = strike_rate
        super().__init__(f"strike rate must be positive, got {strike_rate}")


class NonFiniteStrikeRateError(ValidationError):
    """Raised when a strike rate is NaN or infinite.

    Shared by TradeDetails.strike_rate and Booked.strike_rate, like
    NonPositiveStrikeRateError, and checked before the sign check for the same
    reason as NonFiniteNotionalAmountError.
    """

    def __init__(self, strike_rate: Decimal) -> None:
        self.strike_rate = strike_rate
        super().__init__(f"strike rate must be a finite number, got {strike_rate}")


class NoOpUpdateError(ValidationError):
    """Raised when an update supplies details identical to the current ones.

    The trade-level counterpart of EmptyChangesError: update() computes the
    changed fields itself and refuses to record an Updated event that would
    force reapproval without changing anything.
    """

    def __init__(self) -> None:
        super().__init__("update must change at least one field")


class StrikeBeforeExecutionError(ValidationError):
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

    Deliberately not a TradeError: a lookup miss isn't invalid input or a
    broken trading rule, so callers that catch TradeError to mean "the
    domain refused this" shouldn't also catch a missing trade by accident.
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
