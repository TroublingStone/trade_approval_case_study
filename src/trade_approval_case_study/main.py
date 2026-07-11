from fastapi import FastAPI

app = FastAPI(title="Trade Approval Case Study")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
