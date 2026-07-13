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

    def list(self, *, limit: int | None = None, after: TradeId | None = None) -> list[Trade]:
        """Trades ordered by id (lexicographic -- the cursor order).

        `after` returns only trades with id strictly greater than it, `limit`
        caps the result count; together they support cursor pagination. The
        defaults return everything.
        """
        ...


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

    def list(self, *, limit: int | None = None, after: TradeId | None = None) -> list[Trade]:
        trades = sorted(self._trades.values(), key=lambda trade: trade.id)
        if after is not None:
            trades = [trade for trade in trades if trade.id > after]
        return trades if limit is None else trades[:limit]
