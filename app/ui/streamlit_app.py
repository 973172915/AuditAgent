"""Streamlit 审计分析界面。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from agent.config import settings
from agent.pipeline.graph import export_mermaid, run_agent
from agent.tools.reconciliation import counterparty_analysis, reconciliation_check

st.set_page_config(page_title="AuditAgent", page_icon="🔍", layout="wide")
st.title("🔍 审计数据分析 Agent")
st.caption("自然语言查询银行流水与财务账簿 · 本地模型推理 · 全链路审计留痕")

tab_chat, tab_recon, tab_logs, tab_arch = st.tabs(
    ["💬 智能查询", "🔗 勾稽核对", "📋 审计日志", "📐 架构"]
)

# ─── 侧边栏 ────────────────────────────────
with st.sidebar:
    st.header("⚙️ 配置")
    st.markdown(f"**模型**: `{settings.ollama_model}`")
    st.markdown(f"**Ollama**: `{settings.ollama_base_url}`")
    st.markdown(f"**最大重试**: {settings.max_retries}")
    st.markdown(f"**结果行数上限**: {settings.max_result_rows}")

    st.divider()
    st.markdown("**💡 示例问题：**")
    examples = [
        "查9月份所有金额大于10万的支出",
        "统计9月各对手方的交易总额",
        "找出可能重复的交易记录",
        "深圳市XX贸易有限公司的所有往来明细",
        "9月资金净流入是多少？",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{hash(ex)}"):
            st.session_state["input_query"] = ex

# ─── Tab 1: 智能查询 ────────────────────────────────

with tab_chat:
    query = st.text_input(
        "输入你的问题：",
        value=st.session_state.get("input_query", ""),
        placeholder="例如：查一下9月份金额大于10万的异常往来",
    )
    go = st.button("🚀 执行分析", type="primary", use_container_width=True)

    if go and query.strip():
        with st.status("Agent 运行中...", expanded=True) as status:
            st.write("① 生成 SQL...")
            try:
                result = run_agent(query.strip())
            except Exception as e:
                status.update(label="失败", state="error")
                st.error(f"执行失败：{e}")
                st.stop()
            status.update(label="完成！", state="complete", expanded=False)

        # 结果展示
        if result["success"]:
            st.success(f"✅ 查询成功 | {result['row_count']} 行 | "
                       f"耗时 {result['duration_ms']}ms | 重试 {result['retry_count']} 次")
        else:
            st.error(f"❌ 查询失败: {result.get('error', '未知错误')}")

        # Agent 内部轨迹（可折叠）
        with st.expander("🔧 Agent 内部轨迹（SQL + 执行详情）", expanded=True):
            col_sql, col_info = st.columns([2, 1])
            with col_sql:
                st.markdown("**生成的 SQL：**")
                st.code(result.get("generated_sql") or "N/A", language="sql")
            with col_info:
                st.markdown("**执行信息：**")
                st.json({
                    "成功": result["success"],
                    "行数": result["row_count"],
                    "耗时(ms)": result["duration_ms"],
                    "重试次数": result["retry_count"],
                })

        # 数据表格
        if result.get("data"):
            st.subheader("📊 查询结果")
            df = pd.DataFrame(result["data"])
            st.dataframe(df, use_container_width=True)

            # 导出
            csv_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ 导出 Excel",
                data=csv_data,
                file_name=f"audit_result_{result['session_id']}.csv",
                mime="text/csv",
            )

        # 自然语言总结
        if result.get("summary"):
            st.subheader("📝 分析总结")
            st.markdown(result["summary"])

# ─── Tab 2: 勾稽核对 ────────────────────────────────

with tab_recon:
    st.markdown("比对银行流水与财务账簿的差异，发现漏记或虚记。")
    col1, col2 = st.columns(2)
    date_start = col1.text_input("起始日期", value="2024-09-01")
    date_end = col2.text_input("结束日期", value="2024-10-31")

    if st.button("🔗 执行勾稽核对", type="primary"):
        with st.spinner("核对中..."):
            recon_json = reconciliation_check.invoke({"date_start": date_start, "date_end": date_end})
            recon = json.loads(recon_json)

        # 统计概览
        stats = recon["统计"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("银行支出笔数", stats["银行流水_支出笔数"])
        c2.metric("账簿贷方笔数", stats["账簿_贷方笔数"])
        c3.metric("银行收入笔数", stats["银行流水_收入笔数"])
        c4.metric("账簿借方笔数", stats["账簿_借方笔数"])

        # 支出方向差异
        st.subheader("📤 支出方向")
        out = recon["支出方向"]
        st.markdown(f"**已匹配**: {out['已匹配']} 笔")
        if out["银行有账簿无（可能漏记）"]:
            st.warning(f"⚠️ 银行有但账簿无: {len(out['银行有账簿无（可能漏记）'])} 笔")
            st.dataframe(pd.DataFrame(out["银行有账簿无（可能漏记）"]))
        if out["账簿有银行无（可能虚记）"]:
            st.warning(f"⚠️ 账簿有但银行无: {len(out['账簿有银行无（可能虚记）'])} 笔")
            st.dataframe(pd.DataFrame(out["账簿有银行无（可能虚记）"]))

        # 对手方分析
        st.subheader("👤 对手方快速分析")
        name = st.text_input("输入对手方名称关键词", value="深圳")
        if st.button("分析"):
            cp_json = counterparty_analysis.invoke({
                "account_name": name, "date_start": "", "date_end": ""
            })
            cp = json.loads(cp_json)
            if "error" not in cp:
                c1, c2, c3 = st.columns(3)
                c1.metric("交易笔数", cp["交易笔数"])
                c2.metric("总收入", f"¥{cp['总收入']:,.2f}")
                c3.metric("总支出", f"¥{cp['总支出']:,.2f}")
                st.dataframe(pd.DataFrame(cp["明细"]))
            else:
                st.error(cp["error"])

# ─── Tab 3: 审计日志 ────────────────────────────────

with tab_logs:
    st.markdown("所有操作均记录在 `logs/audit_log.jsonl` 中，支持完整追溯。")
    log_path = settings.audit_log_path
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        entries = [json.loads(l) for l in lines[-50:]]  # 最近 50 条
        df = pd.DataFrame(entries)
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "⬇️ 下载完整日志",
            data=log_path.read_bytes(),
            file_name="audit_log.jsonl",
        )
    else:
        st.info("暂无日志，执行一次查询后这里会显示操作记录。")

# ─── Tab 4: 架构图 ────────────────────────────────

with tab_arch:
    st.subheader("LangGraph Agent 状态机")
    st.caption("粘贴到 https://mermaid.live 预览")
    st.code(export_mermaid(), language="mermaid")
