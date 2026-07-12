from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, ClassVar

from .enums import State
from .errors import (
    EmptyChangesError,
    NaiveEventTimestampError,
    NegativeEventSeqError,
    NonPositiveStrikeRateError,
)
from .trade_details import TradeDetails
from .types import UserId

__all__ = [
    "State",
    "UserId",
    "Event",
    "Submitted",
    "Approved",
    "Updated",
    "Cancelled",
    "SentToExecute",
    "Booked",
    "ActionRecord",
]


@dataclass(frozen=True, kw_only=True)
class Event:
    action: ClassVar[str]

    seq: int
    user_id: UserId
    timestamp: datetime

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.seq < 0:
            raise NegativeEventSeqError(self.seq)
        if self.timestamp.tzinfo is None:
            raise NaiveEventTimestampError(self.timestamp)


@dataclass(frozen=True, kw_only=True)
class Submitted(Event):
    action = "Submit"
    details: TradeDetails


@dataclass(frozen=True, kw_only=True)
class Approved(Event):
    action = "Approve"


@dataclass(frozen=True, kw_only=True)
class Updated(Event):
    action = "Update"

    changes: Mapping[str, Any]

    def __post_init__(self) -> None:
        self._validate()
        object.__setattr__(self, "changes", MappingProxyType(dict(self.changes)))

    def _validate(self) -> None:
        super()._validate()
        if not self.changes:
            raise EmptyChangesError()


@dataclass(frozen=True, kw_only=True)
class Cancelled(Event):
    action = "Cancel"


@dataclass(frozen=True, kw_only=True)
class SentToExecute(Event):
    action = "SendToExecute"


@dataclass(frozen=True, kw_only=True)
class Booked(Event):
    action = "Book"
    strike_rate: Decimal
    confirmation: str

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        super()._validate()
        if self.strike_rate <= 0:
            raise NonPositiveStrikeRateError(self.strike_rate)


@dataclass(frozen=True, kw_only=True)
class ActionRecord:
    seq: int
    action: str
    user_id: UserId
    timestamp: datetime
    state_before: State
    state_after: State
