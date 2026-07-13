import logging
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

logger = logging.getLogger(__name__)

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
        if status_code >= 500:
            logger.error("internal error on %s %s", request.method, request.url.path, exc_info=exc)
            return JSONResponse(status_code=status_code, content={"detail": "Internal Server Error"})
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler
