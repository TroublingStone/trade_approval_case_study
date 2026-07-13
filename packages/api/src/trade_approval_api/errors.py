from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from trade_approval_core.errors import (
    ConcurrentModificationError,
    CorruptEventLogError,
    InvalidSeqError,
    InvalidTransitionError,
    MissingTradeDetailsError,
    TradeNotFoundError,
    UnauthorizedActionError,
)
from trade_approval_core.errors import ValidationError as CoreValidationError

_EXCEPTION_STATUS: dict[type[Exception], int] = {
    CoreValidationError: 422,
    InvalidTransitionError: 409,
    ConcurrentModificationError: 409,
    UnauthorizedActionError: 403,
    InvalidSeqError: 404,
    TradeNotFoundError: 404,
    MissingTradeDetailsError: 500,
    CorruptEventLogError: 500,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, status_code in _EXCEPTION_STATUS.items():
        app.add_exception_handler(exc_type, _handler_for(status_code))


def _handler_for(status_code: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler
