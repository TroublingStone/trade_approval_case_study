from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from trade_approval_api.errors import register_exception_handlers
from trade_approval_api.routes import router as trades_router
from trade_approval_api.settings import Settings
from trade_approval_api.sqlite_store import SqliteTradeStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        store = SqliteTradeStore(settings.database_path)
        app.state.store = store
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="Trade Approval API", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(trades_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
