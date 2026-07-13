from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from trade_approval_core.trade import Trade
from trade_approval_core.types import TradeId

from trade_approval_api.constants import TRADES_PREFIX
from trade_approval_api.dependencies import StoreDep, UserDep
from trade_approval_api.schemas import (
    BookRequest,
    DiffOut,
    ErrorDetail,
    HistoryEntryOut,
    TradeDetailsIn,
    TradeDetailsOut,
    TradeOut,
    TradePageOut,
)

router = APIRouter(prefix=TRADES_PREFIX, tags=["trades"])

_Responses = dict[int | str, dict[str, Any]]
_UNAUTHORIZED: _Responses = {401: {"model": ErrorDetail, "description": "Missing X-User-Id header"}}
_FORBIDDEN: _Responses = {403: {"model": ErrorDetail, "description": "Caller may not take this action"}}
_NOT_FOUND: _Responses = {404: {"model": ErrorDetail, "description": "No such trade, or referenced version"}}
_CONFLICT: _Responses = {
    409: {"model": ErrorDetail, "description": "Action invalid from the current state, or a concurrent modification"}
}
_WRITE_ERRORS: _Responses = {**_UNAUTHORIZED, **_FORBIDDEN, **_NOT_FOUND, **_CONFLICT}


@router.post("", status_code=201, responses=_UNAUTHORIZED)
async def submit_trade(
    body: TradeDetailsIn, user: UserDep, store: StoreDep, request: Request, response: Response
) -> TradeOut:
    trade = Trade()
    trade.submit(user, body.to_core())
    store.save(trade)
    response.headers["Location"] = request.app.url_path_for("get_trade", trade_id=trade.id)
    return TradeOut.from_trade(trade)


@router.get("")
async def list_trades(
    store: StoreDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after: Annotated[TradeId | None, Query()] = None,
) -> TradePageOut:
    trades = store.list(limit=limit + 1, after=after)
    page = trades[:limit]
    next_cursor = page[-1].id if len(trades) > limit else None
    return TradePageOut(items=[TradeOut.from_trade(trade) for trade in page], next_cursor=next_cursor)


@router.get("/{trade_id}", responses=_NOT_FOUND)
async def get_trade(trade_id: TradeId, store: StoreDep) -> TradeOut:
    return TradeOut.from_trade(store.get(trade_id))


@router.post("/{trade_id}/approve", responses=_WRITE_ERRORS)
async def approve_trade(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.accept(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/update", responses=_WRITE_ERRORS)
async def update_trade(trade_id: TradeId, body: TradeDetailsIn, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.update(user, body.to_core())
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/cancel", responses=_WRITE_ERRORS)
async def cancel_trade(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.cancel(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/send-to-execute", responses=_WRITE_ERRORS)
async def send_trade_to_execute(trade_id: TradeId, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.send_to_execute(user)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.post("/{trade_id}/book", responses=_WRITE_ERRORS)
async def book_trade(trade_id: TradeId, body: BookRequest, user: UserDep, store: StoreDep) -> TradeOut:
    trade = store.get(trade_id)
    trade.book(user, body.strike_rate, body.confirmation)
    store.save(trade)
    return TradeOut.from_trade(trade)


@router.get("/{trade_id}/history", responses=_NOT_FOUND)
async def get_trade_history(trade_id: TradeId, store: StoreDep) -> list[HistoryEntryOut]:
    trade = store.get(trade_id)
    return [HistoryEntryOut.from_core(record) for record in trade.history()]


@router.get("/{trade_id}/details/{seq}", responses=_NOT_FOUND)
async def get_trade_details_as_of(trade_id: TradeId, seq: int, store: StoreDep) -> TradeDetailsOut:
    trade = store.get(trade_id)
    return TradeDetailsOut.from_core(trade.details_as_of(seq))


@router.get("/{trade_id}/diff", responses=_NOT_FOUND)
async def diff_trade(
    trade_id: TradeId,
    store: StoreDep,
    seq_from: Annotated[int, Query(alias="from")],
    seq_to: Annotated[int, Query(alias="to")],
) -> DiffOut:
    trade = store.get(trade_id)
    return trade.diff(seq_from, seq_to)
