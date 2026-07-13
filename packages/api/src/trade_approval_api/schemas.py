from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from trade_approval_core.enums import Currency, Direction, State, Style
from trade_approval_core.errors import MissingTradeDetailsError
from trade_approval_core.events import ActionRecord
from trade_approval_core.trade import Trade
from trade_approval_core.trade_details import TradeDetails
from trade_approval_core.types import TradeId, UserId


class TradeDetailsIn(BaseModel):

    model_config = ConfigDict(extra="forbid")
    trading_entity: str
    counterparty: str
    direction: Direction
    style: Style = Style.FORWARD
    notional_currency: Currency
    notional_amount: Decimal
    underlying: tuple[Currency, Currency]
    trade_date: date
    value_date: date
    delivery_date: date

    def to_core(self) -> TradeDetails:
        return TradeDetails(**self.model_dump())


class TradeDetailsOut(BaseModel):
    trading_entity: str
    counterparty: str
    direction: Direction
    style: Style
    notional_currency: Currency
    notional_amount: Decimal
    underlying: tuple[Currency, Currency]
    trade_date: date
    value_date: date
    delivery_date: date
    strike_rate: Decimal | None = None

    @classmethod
    def from_core(cls, details: TradeDetails) -> "TradeDetailsOut":
        return cls.model_validate(details, from_attributes=True)


class TradeOut(BaseModel):
    id: TradeId
    state: State
    requester: UserId | None
    approver: UserId | None
    details: TradeDetailsOut

    @classmethod
    def from_trade(cls, trade: Trade) -> "TradeOut":
        details = trade.details
        if details is None:
            raise MissingTradeDetailsError(trade.id)
        return cls(
            id=trade.id,
            state=trade.state,
            requester=trade.requester,
            approver=trade.approver,
            details=TradeDetailsOut.from_core(details),
        )


class BookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strike_rate: Decimal
    confirmation: str


class HistoryEntryOut(BaseModel):
    seq: int
    action: str
    user_id: UserId
    timestamp: datetime
    state_before: State
    state_after: State

    @classmethod
    def from_core(cls, record: ActionRecord) -> "HistoryEntryOut":
        return cls.model_validate(record, from_attributes=True)


FieldValue = Decimal | date | Direction | Style | Currency | tuple[Currency, Currency] | str | None
DiffOut = dict[str, tuple[FieldValue, FieldValue]]
