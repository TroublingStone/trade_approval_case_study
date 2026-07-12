from .errors import TradeNotFoundError
from .trade import Trade
from .types import TradeId


class TradeStore:
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
