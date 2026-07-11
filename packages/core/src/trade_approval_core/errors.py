from datetime import date, datetime
from decimal import Decimal

from .enums import Currency
from .types import TradeId


class ValidationError(Exception):
    """Base class for all domain validation errors."""


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


class NotionalCurrencyMismatchError(ValidationError):
    """Raised when the notional currency is not part of the underlying pair."""

    def __init__(self, notional_currency: Currency, underlying: tuple[Currency, Currency]) -> None:
        self.notional_currency = notional_currency
        self.underlying = underlying
        super().__init__(
            f"notional currency {notional_currency} must be part of "
            f"the underlying {underlying}"
        )


class NonPositiveStrikeRateError(ValidationError):
    """Raised when the strike rate is not strictly positive."""

    def __init__(self, strike_rate: Decimal) -> None:
        self.strike_rate = strike_rate
        super().__init__(f"strike rate must be positive, got {strike_rate}")


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


class NonPositiveStrikeError(ValidationError):
    """Raised when a Booked event's strike is not strictly positive."""

    def __init__(self, strike: Decimal) -> None:
        self.strike = strike
        super().__init__(f"strike must be positive, got {strike}")


class TradeNotFoundError(Exception):
    """Raised when no trade exists for a given id."""

    def __init__(self, trade_id: TradeId) -> None:
        self.trade_id = trade_id
        super().__init__(f"no trade found for id {trade_id}")
