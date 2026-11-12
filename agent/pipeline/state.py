"""Agent 状态定义。"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph Agent 的共享状态。"""

    # 输入
    user_query: str
    session_id: str

    # 中间产物
    schema_text: str           # 表结构描述
    generated_sql: str         # LLM 生成的 SQL
    execution_result: dict     # 执行结果 {success, data, error, row_count, duration_ms}
    summary: str               # 自然语言总结

    # 错误处理
    error: str
    retry_count: int

    # 审计日志
    log_entry: dict[str, Any]
