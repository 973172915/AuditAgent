"""DuckDB SQL 执行工具（含安全护栏）。"""
import re
import time
from pathlib import Path

import duckdb
import pandas as pd
from langchain_core.tools import tool

from agent.config import settings


class SQLExecutor:
    """安全的 DuckDB 查询执行器。

    安全措施：
    1. 只允许 SELECT 语句
    2. 表名白名单
    3. 强制 LIMIT 上限
    4. 查询超时控制
    """

    def __init__(self):
        self.conn = duckdb.connect()
        self._register_tables()

    def _register_tables(self):
        """将 CSV 注册为可查询视图。"""
        if settings.bank_statement_path.exists():
            self.conn.execute(
                f"CREATE VIEW bank_statement AS SELECT * FROM read_csv_auto('{settings.bank_statement_path.as_posix()}')"
            )
        if settings.ledger_path.exists():
            self.conn.execute(
                f"CREATE VIEW ledger AS SELECT * FROM read_csv_auto('{settings.ledger_path.as_posix()}')"
            )

    def validate_sql(self, sql: str) -> tuple[bool, str]:
        """校验 SQL 安全性，返回 (是否合法, 原因)。"""
        sql_upper = sql.strip().upper()

        # 1. 只允许 SELECT
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return False, "只允许 SELECT 或 WITH 开头的查询语句"

        # 2. 禁止危险关键字
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXECUTE"]
        for kw in dangerous:
            if re.search(rf"\b{kw}\b", sql_upper):
                return False, f"禁止使用 {kw} 语句"

        # 3. 表名白名单
        whitelist = [t.strip() for t in settings.sql_whitelist_tables.split(",")]
        # 提取 FROM/JOIN 后的表名
        table_refs = re.findall(r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.IGNORECASE)
        for t in table_refs:
            if t.lower() not in whitelist:
                return False, f"不允许访问表 '{t}'，只允许：{whitelist}"

        # 4. 注入 LIMIT
        if not re.search(r"\bLIMIT\s+\d+", sql_upper):
            sql = sql.rstrip().rstrip(";") + f" LIMIT {settings.max_result_rows}"

        return True, sql

    def execute(self, sql: str) -> dict:
        """执行 SQL 并返回结果。

        Returns:
            {"success": bool, "data": list | None, "error": str | None,
             "row_count": int, "duration_ms": int}
        """
        is_valid, result_or_error = self.validate_sql(sql)
        if not is_valid:
            return {
                "success": False,
                "data": None,
                "error": f"[安全拦截] {result_or_error}",
                "row_count": 0,
                "duration_ms": 0,
            }

        final_sql = result_or_error  # 可能被注入了 LIMIT

        start = time.perf_counter()
        try:
            df = self.conn.execute(final_sql).fetchdf()
            duration_ms = int((time.perf_counter() - start) * 1000)

            return {
                "success": True,
                "data": df.to_dict(orient="records"),
                "columns": list(df.columns),
                "error": None,
                "row_count": len(df),
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "row_count": 0,
                "duration_ms": duration_ms,
            }

    def get_schema_text(self) -> str:
        """获取所有表的 schema 文本描述（供 LLM 使用）。"""
        import yaml
        with open(settings.schema_path, encoding="utf-8") as f:
            schema = yaml.safe_load(f)

        lines = []
        for tname, tinfo in schema["tables"].items():
            lines.append(f"\n## 表: {tname}")
            lines.append(f"描述: {tinfo['description']}")
            for col in tinfo["columns"]:
                lines.append(f"  - {col['name']} ({col['type']}): {col['description']}")

        if "examples" in schema:
            lines.append("\n## 示例查询")
            for ex in schema["examples"]:
                lines.append(f"问题: {ex['query']}")
                lines.append(f"SQL: {ex['sql']}")

        return "\n".join(lines)

    def close(self):
        self.conn.close()


# 单例
_executor: SQLExecutor | None = None


def get_executor() -> SQLExecutor:
    global _executor
    if _executor is None:
        _executor = SQLExecutor()
    return _executor


@tool
def execute_sql(query: str) -> str:
    """执行 SQL 查询并返回结果。

    Args:
        query: 要执行的 SELECT SQL 语句

    Returns:
        JSON 格式的查询结果或错误信息
    """
    import json
    executor = get_executor()
    result = executor.execute(query)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_table_schema() -> str:
    """获取所有数据表的字段结构说明，用于了解可以查询哪些字段。"""
    return get_executor().get_schema_text()
