"""FastAPI 接口。"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.pipeline.graph import export_mermaid, run_agent
from agent.tools.reconciliation import counterparty_analysis, reconciliation_check

app = FastAPI(title="AuditAgent", description="审计数据分析 Agent", version="0.1.0")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    session_id: str | None = None


@app.post("/api/query")
def query(req: QueryRequest):
    """自然语言查询接口。"""
    try:
        result = run_agent(req.query, req.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(result)


@app.post("/api/reconciliation")
def reconciliation(date_start: str = "", date_end: str = ""):
    """勾稽核对接口。"""
    try:
        result = reconciliation_check.invoke({"date_start": date_start, "date_end": date_end})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(content=result)


@app.get("/api/counterparty/{account_name}")
def counterparty(account_name: str, date_start: str = "", date_end: str = ""):
    """对手方分析接口。"""
    try:
        result = counterparty_analysis.invoke({
            "account_name": account_name,
            "date_start": date_start,
            "date_end": date_end,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(content=result)


@app.get("/api/graph/mermaid")
def graph_mermaid():
    return {"mermaid": export_mermaid()}


@app.get("/api/health")
def health():
    return {"status": "ok"}
