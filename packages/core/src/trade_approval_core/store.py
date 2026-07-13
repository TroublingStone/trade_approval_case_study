from typing import Protocol

from .errors import TradeNotFoundError
from .trade import Trade
from .types import TradeId


class TradeStore(Protocol):
    """Persistence contract for Trade aggregates.

    Implementations may be in-memory (InMemoryTradeStore) or durable (e.g. a
    SQLite-backed event store) -- callers depend only on this shape.
    """

    def save(self, trade: Trade) -> None: ...

    def get(self, trade_id: TradeId) -> Trade:
        """Raise TradeNotFoundError if no trade exists for trade_id."""
        ...

    def list(self) -> list[Trade]: ...


class InMemoryTradeStore:
    def __init__(self) -> None:
        self._trades: dict[TradeId, Trade] = {}

    def save(self, trade: Trade) -> None:
        self._trades[trade.id] = trade

    def get(self, trade_id: TradeId) -> Trade:
        try:
            return self._trades[trade_id]
        except KeyError:
            raise TradeNotFoundError(trade_id) from None

    def list(self) -> list[Trade]:
        return list(self._trades.values())
