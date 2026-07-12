from fastapi import FastAPI
from pydantic import BaseModel
from trade_approval_core import TradeApprovalResult, evaluate_trade

app = FastAPI(title="Trade Approval API")


class TradeApprovalRequest(BaseModel):
    amount: float
    limit: float


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/evaluate")
async def evaluate(request: TradeApprovalRequest) -> TradeApprovalResult:
    return evaluate_trade(request.amount, request.limit)
