"""评测脚本：批量运行测试用例，统计 Agent 表现。

用法：
    python eval/run_eval.py
"""
import sys
import time
from pathlib import Path

import yaml

# 确保能导入项目模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.pipeline.graph import run_agent  # noqa: E402


def load_cases() -> list[dict]:
    path = ROOT / "eval" / "test_queries.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["cases"]


def evaluate_case(case: dict) -> dict:
    """运行单个用例并评估结果。"""
    query = case["query"]
    expect = case.get("expect", {})

    start = time.perf_counter()
    try:
        result = run_agent(query)
    except Exception as e:
        return {
            "id": case["id"],
            "query": query,
            "status": "ERROR",
            "error": str(e)[:200],
            "duration_s": round(time.perf_counter() - start, 1),
        }

    duration_s = round(time.perf_counter() - start, 1)

    if not result.get("success"):
        return {
            "id": case["id"],
            "query": query,
            "status": "FAILED",
            "sql": result.get("generated_sql", ""),
            "error": result.get("error", "")[:200],
            "retries": result.get("retry_count", 0),
            "duration_s": duration_s,
        }

    row_count = result.get("row_count", 0)
    columns = result.get("columns", [])

    # 验证期望
    checks = []
    if "min_rows" in expect:
        checks.append(("行数>=阈值", row_count >= expect["min_rows"]))
    if "must_contain_columns" in expect:
        missing = [c for c in expect["must_contain_columns"] if c not in columns]
        checks.append(("包含必要列", len(missing) == 0))

    passed = all(ok for _, ok in checks)

    return {
        "id": case["id"],
        "query": query,
        "status": "PASS" if passed else "PARTIAL",
        "rows": row_count,
        "retries": result.get("retry_count", 0),
        "duration_s": duration_s,
        "checks": {name: "✅" if ok else "❌" for name, ok in checks},
        "sql_preview": (result.get("generated_sql") or "")[:100],
    }


def main():
    print("=" * 70)
    print("审计 Agent 评测")
    print("=" * 70)

    cases = load_cases()
    results = []

    for case in cases:
        print(f"\n▶ {case['id']}: {case['query']}")
        result = evaluate_case(case)
        results.append(result)

        status_icon = {"PASS": "✅", "PARTIAL": "⚠️", "FAILED": "❌", "ERROR": "💥"}.get(
            result["status"], "?"
        )
        print(f"  {status_icon} {result['status']} | {result.get('rows', '-')} 行 | "
              f"重试={result.get('retries', 0)} | {result['duration_s']}s")

    # 汇总
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] in ("FAILED", "ERROR"))
    avg_retries = sum(r.get("retries", 0) for r in results) / total
    avg_duration = sum(r.get("duration_s", 0) for r in results) / total

    print(f"  总用例: {total}")
    print(f"  通过:   {passed} ({passed/total*100:.0f}%)")
    print(f"  部分:   {partial}")
    print(f"  失败:   {failed}")
    print(f"  平均重试: {avg_retries:.1f}")
    print(f"  平均耗时: {avg_duration:.1f}s")

    # 保存报告
    report_path = ROOT / "eval" / "report.json"
    import json
    report_path.write_text(json.dumps({
        "summary": {
            "total": total, "passed": passed, "partial": partial,
            "failed": failed, "avg_retries": avg_retries, "avg_duration_s": avg_duration,
        },
        "details": results,
    }, ensure_ascii=False, indent=2))
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
