"""Agent 各节点实现：Text-to-SQL → 执行 → 修复 → 总结。"""
import json
import time
import uuid
from datetime import datetime

import ollama

from agent.config import settings
from agent.pipeline.state import AgentState
from agent.tools.sql_executor import get_executor


def _call_llm(system: str, user: str) -> str:
    """调用 Ollama 本地模型。"""
    client = ollama.Client(host=settings.ollama_base_url)
    resp = client.chat(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0.1},  # 低温度，保证 SQL 稳定性
    )
    return resp["message"]["content"].strip()


def _log_audit(state: AgentState, event: str, extra: dict | None = None):
    """写入审计日志（JSONL 格式）。"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": state.get("session_id", ""),
        "event": event,
        "user_query": state.get("user_query", ""),
        "model": settings.ollama_model,
        **(extra or {}),
    }
    with open(settings.audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── 节点 1：生成 SQL ────────────────────────────────

SYSTEM_PROMPT_SQL = """你是一名专业的审计数据分析师。根据用户的自然语言问题和数据库表结构，生成对应的 SELECT SQL 查询。

规则：
1. 只能使用提供的表和字段名（注意字段名是中文的）
2. 只生成 SELECT 语句，禁止任何修改数据的操作
3. 金额计算要考虑精度，必要时用 CAST(x AS DECIMAL(18,2))
4. 结果按相关性排序
5. 只输出 SQL 代码，不要 markdown 代码块，不要解释
"""


def node_generate_sql(state: AgentState) -> AgentState:
    executor = get_executor()
    schema_text = executor.get_schema_text()

    user_msg = f"""## 数据库表结构
{schema_text}

## 用户问题
{state['user_query']}

请直接输出 SQL（只输出 SQL 代码本身）："""

    sql = _call_llm(SYSTEM_PROMPT_SQL, user_msg)

    # 清理可能的 markdown 包裹
    if sql.startswith("```"):
        sql = sql.strip("`")
        if sql.lower().startswith("sql"):
            sql = sql[3:]
        sql = sql.strip()

    _log_audit(state, "generate_sql", {"sql": sql, "retry_count": state.get("retry_count", 0)})

    return {
        "generated_sql": sql,
        "schema_text": schema_text,
    }


# ─── 节点 2：执行 SQL ────────────────────────────────

def node_execute_sql(state: AgentState) -> AgentState:
    executor = get_executor()
    sql = state["generated_sql"]

    result = executor.execute(sql)

    _log_audit(state, "execute_sql", {
        "sql": sql,
        "success": result["success"],
        "row_count": result.get("row_count", 0),
        "duration_ms": result.get("duration_ms", 0),
        "error": result.get("error"),
    })

    return {
        "execution_result": result,
        "error": result.get("error"),
    }


# ─── 节点 3：修复 SQL ────────────────────────────────

def node_fix_sql(state: AgentState) -> AgentState:
    error = state.get("error", "")
    old_sql = state["generated_sql"]
    retry_count = state.get("retry_count", 0) + 1

    fix_prompt = f"""你之前生成的 SQL 执行失败了，请修复它。

原始 SQL：
{old_sql}

错误信息：
{error}

请分析错误原因并输出修正后的完整 SQL（只输出 SQL 代码）："""

    fixed_sql = _call_llm("你是 SQL 专家，擅长分析和修复 SQL 错误。只输出修正后的 SQL 代码。", fix_prompt)

    if fixed_sql.startswith("```"):
        fixed_sql = fixed_sql.strip("`")
        if fixed_sql.lower().startswith("sql"):
            fixed_sql = fixed_sql[3:]
        fixed_sql = fixed_sql.strip()

    _log_audit(state, "fix_sql", {
        "old_sql": old_sql,
        "fixed_sql": fixed_sql,
        "error": error,
        "retry_count": retry_count,
    })

    return {
        "generated_sql": fixed_sql,
        "retry_count": retry_count,
    }


# ─── 节点 4：总结结果 ────────────────────────────────

def node_summarize(state: AgentState) -> AgentState:
    result = state["execution_result"]
    if not result or not result.get("success"):
        error = result.get("error", "未知错误") if result else "无执行结果"
        retry_count = state.get("retry_count", 0)
        msg = f"查询在 {retry_count} 次修复后仍然失败。错误信息：{error}"
        return {"summary": msg}

    data = result.get("data", [])
    row_count = result.get("row_count", 0)

    if row_count == 0:
        return {"summary": "查询执行成功，但没有匹配的记录。"}

    # 取前 20 行给 LLM 总结（避免 token 过多）
    sample_data = data[:20]

    prompt = f"""以下是一条审计查询的结果（共 {row_count} 行，展示前 {len(sample_data)} 行）：

{json.dumps(sample_data, ensure_ascii=False, default=str)}

请用简洁的中文总结这个结果的关键发现，包括：
1. 总体情况概述
2. 值得关注的异常或大额项
3. 建议的后续审计动作（如有）

直接输出总结文字："""

    summary = _call_llm("你是审计数据分析专家，善于从数据中发现关键信息。", prompt)

    _log_audit(state, "summarize", {"row_count": row_count, "summary_length": len(summary)})

    return {"summary": summary}
