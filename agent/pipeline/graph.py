"""LangGraph Agent 编排：Text-to-SQL + 自动修复 + 总结。"""
from langgraph.graph import END, StateGraph

from agent.config import settings
from agent.pipeline.nodes import (
    node_execute_sql,
    node_fix_sql,
    node_generate_sql,
    node_summarize,
)
from agent.pipeline.state import AgentState


def _should_continue(state: AgentState) -> str:
    """条件路由：执行成功→总结，失败→判断是否重试。"""
    result = state.get("execution_result", {})
    if result.get("success"):
        return "summarize"

    retry_count = state.get("retry_count", 0)
    if retry_count < settings.max_retries:
        return "fix"
    return "summarize"  # 超过重试次数也走 summarize 输出错误信息


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("generate_sql", node_generate_sql)
    g.add_node("execute_sql", node_execute_sql)
    g.add_node("fix_sql", node_fix_sql)
    g.add_node("summarize", node_summarize)

    g.set_entry_point("generate_sql")
    g.add_edge("generate_sql", "execute_sql")

    # 条件分支：成功→总结，失败→修复或放弃（都走 summarize）
    g.add_conditional_edges(
        "execute_sql",
        _should_continue,
        {"summarize": "summarize", "fix": "fix_sql"},
    )

    # 修复后重新执行
    g.add_edge("fix_sql", "execute_sql")

    g.add_edge("summarize", END)

    return g.compile()


app = build_graph()


def run_agent(user_query: str, session_id: str | None = None) -> dict:
    """对外入口：运行审计分析 Agent。"""
    init_state: AgentState = {
        "user_query": user_query,
        "session_id": session_id or uuid.uuid4().hex[:8],
        "retry_count": 0,
    }
    result = app.invoke(init_state)

    execution = result.get("execution_result", {})
    return {
        "session_id": init_state["session_id"],
        "user_query": user_query,
        "generated_sql": result.get("generated_sql"),
        "success": execution.get("success", False),
        "data": execution.get("data"),
        "columns": execution.get("columns"),
        "row_count": execution.get("row_count", 0),
        "duration_ms": execution.get("duration_ms", 0),
        "summary": result.get("summary"),
        "error": result.get("error"),
        "retry_count": result.get("retry_count", 0),
    }


import uuid  # noqa: E402


def export_mermaid() -> str:
    return app.get_graph().draw_mermaid()
