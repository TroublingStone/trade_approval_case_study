from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from trade_approval_core.trade import Trade
from trade_approval_core.types import TradeId

from trade_approval_api.constants import TRADES_PREFIX
from trade_approval_api.dependencies import StoreDep, UserDep
from trade_approval_api.schemas import (
    BookRequest,
    DiffOut,
    HistoryEntryOut,
    TradeDetailsIn,
    TradeDetailsOut,
    TradeOut,
)

router = APIRouter(prefix=TRADES_PREFIX, tags=["trades"])


@router.post("", status_code=201)
async def submit_trade(
    body: TradeDetailsIn, user: UserDep, store: StoreDep, request: Request, response: Response
) -> TradeOut:
    trade = Trade()
    trade.submit(user, body.to_core())
    store.save(trade)
    response.headers["Location"] = request.app.url_path_for("get_trade", trade_id=trade.id)
    return TradeOut.from_trade(trade)


@router.get("")
async def list_trades(store: StoreDep) -> list[TradeOut]:
    return [TradeOut.from_trade(trade) for trade in store.list()]


@router.get("/{trade_id}")
async def get_trade(trade_id: TradeId, store: StoreDep) -> TradeOut:
    return TradeOut.from_trade(store.get(trade_id))


@router.post("/{trade_id}/approve")
async def approve_trade(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.accept(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/update")
async def update_trade(trade_id: TradeId, body: TradeDetailsIn, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.update(user, body.to_core())
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/cancel")
async def cancel_trade(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.cancel(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/send-to-execute")
async def send_trade_to_execute(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.send_to_execute(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/book")
async def book_trade(trade_id: TradeId, body: BookRequest, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.book(user, body.strike_rate, body.confirmation)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.get("/{trade_id}/history")
async def get_trade_history(trade_id: TradeId, store: StoreDep) -> list[HistoryEntryOut]:
    trade = store.get(trade_id)
    return [HistoryEntryOut.from_core(record) for record in trade.history()]


@router.get("/{trade_id}/details/{seq}")
async def get_trade_details_as_of(trade_id: TradeId, seq: int, store: StoreDep) -> TradeDetailsOut:
    trade = store.get(trade_id)
    return TradeDetailsOut.from_core(trade.details_as_of(seq))


@router.get("/{trade_id}/diff")
async def diff_trade(
    trade_id: TradeId,
    store: StoreDep,
    seq_from: Annotated[int, Query(alias="from")],
    seq_to: Annotated[int, Query(alias="to")],
) -> DiffOut:
    trade = store.get(trade_id)
    return trade.diff(seq_from, seq_to)
