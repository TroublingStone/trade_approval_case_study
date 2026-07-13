from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from trade_approval_core.store import TradeStore
from trade_approval_core.types import UserId

from trade_approval_api.constants import USER_ID_HEADER


def get_store(request: Request) -> TradeStore:
    store: TradeStore = request.app.state.store
    return store


def get_current_user(user_id: Annotated[str | None, Header(alias=USER_ID_HEADER)] = None) -> UserId:
    if not user_id:
        raise HTTPException(status_code=401, detail=f"{USER_ID_HEADER} header required")
    return UserId(user_id)


StoreDep = Annotated[TradeStore, Depends(get_store)]
UserDep = Annotated[UserId, Depends(get_current_user)]
