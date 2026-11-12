"""勾稽核对工具：银行流水 vs 财务账簿差异分析。"""
import pandas as pd
from langchain_core.tools import tool

from agent.config import settings
from agent.tools.data_cleaner import standardize_bank_statement, standardize_ledger


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    bank = pd.read_csv(settings.bank_statement_path)
    ledger = pd.read_csv(settings.ledger_path)
    return standardize_bank_statement(bank), standardize_ledger(ledger)


@tool
def reconciliation_check(date_start: str = "", date_end: str = "") -> str:
    """勾稽核对：比对银行流水与财务账簿的差异。

    按 (日期, 金额, 对方单位) 三要素匹配，找出：
    - 已匹配交易（两边都有）
    - 银行有但账簿无（可能漏记）
    - 账簿有但银行无（可能虚记）

    Args:
        date_start: 起始日期 YYYY-MM-DD（可选）
        date_end: 结束日期 YYYY-MM-DD（可选）

    Returns:
        JSON 格式的核对结果
    """
    import json

    bank, ledger = _load_data()

    # 日期过滤
    if date_start:
        bank = bank[bank["交易日期"] >= date_start]
        ledger = ledger[ledger["记账日期"] >= date_start]
    if date_end:
        bank = bank[bank["交易日期"] <= date_end]
        ledger = ledger[ledger["记账日期"] <= date_end]

    # 构建匹配键：金额 + 辅助核算/对方户名
    # 银行流水的支出对应账簿的贷方，收入对应借方
    bank_out = bank[bank["出账金额"] > 0][["交易日期", "出账金额", "对方户名"]].copy()
    bank_out.columns = ["日期", "金额", "对方"]
    bank_in = bank[bank["入账金额"] > 0][["交易日期", "入账金额", "对方户名"]].copy()
    bank_in.columns = ["日期", "金额", "对方"]

    ledger_out = ledger[ledger["贷方金额"] > 0][["记账日期", "贷方金额", "辅助核算"]].copy()
    ledger_out.columns = ["日期", "金额", "对方"]
    ledger_in = ledger[ledger["借方金额"] > 0][["记账日期", "借方金额", "辅助核算"]].copy()
    ledger_in.columns = ["日期", "金额", "对方"]

    def fuzzy_match(bank_df, ledger_df):
        """模糊匹配：同金额且对方名称包含关系。"""
        matched = []
        bank_only = []
        used_ledger_idx = set()

        for _, b_row in bank_df.iterrows():
            found = False
            for idx, l_row in ledger_df.iterrows():
                if idx in used_ledger_idx:
                    continue
                # 金额相等 且 对方名称互相包含
                if abs(b_row["金额"] - l_row["金额"]) < 0.01:
                    if (b_row["对方"] in l_row["对方"]) or (l_row["对方"] in b_row["对方"]):
                        matched.append({
                            "日期": b_row["日期"],
                            "金额": float(b_row["金额"]),
                            "银行对方": b_row["对方"],
                            "账簿对方": l_row["对方"],
                        })
                        used_ledger_idx.add(idx)
                        found = True
                        break
            if not found:
                bank_only.append({
                    "日期": b_row["日期"],
                    "金额": float(b_row["金额"]),
                    "对方": b_row["对方"],
                })

        ledger_only = ledger_df[~ledger_df.index.isin(used_ledger_idx)]
        ledger_only_list = [
            {"日期": r["日期"], "金额": float(r["金额"]), "对方": r["对方"]}
            for _, r in ledger_only.iterrows()
        ]
        return matched, bank_only, ledger_only_list

    out_matched, out_bank_only, out_ledger_only = fuzzy_match(bank_out, ledger_out)
    in_matched, in_bank_only, in_ledger_only = fuzzy_match(bank_in, ledger_in)

    result = {
        "统计": {
            "银行流水_支出笔数": len(bank_out),
            "账簿_贷方笔数": len(ledger_out),
            "银行流水_收入笔数": len(bank_in),
            "账簿_借方笔数": len(ledger_in),
        },
        "支出方向": {
            "已匹配": len(out_matched),
            "银行有账簿无（可能漏记）": out_bank_only,
            "账簿有银行无（可能虚记）": out_ledger_only,
        },
        "收入方向": {
            "已匹配": len(in_matched),
            "银行有账簿无（可能漏记）": in_bank_only,
            "账簿有银行无（可能虚记）": in_ledger_only,
        },
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def counterparty_analysis(account_name: str, date_start: str = "", date_end: str = "") -> str:
    """对手账户分析：统计指定对手方的所有交易汇总。

    Args:
        account_name: 对手方名称（支持模糊匹配）
        date_start: 起始日期（可选）
        date_end: 结束日期（可选）

    Returns:
        JSON 格式的交易汇总和明细
    """
    import json

    bank, _ = _load_data()

    if date_start:
        bank = bank[bank["交易日期"] >= date_start]
    if date_end:
        bank = bank[bank["交易日期"] <= date_end]

    # 模糊匹配对手方
    mask = bank["对方户名"].str.contains(account_name, na=False)
    df = bank[mask]

    if df.empty:
        return json.dumps({"error": f"未找到包含 '{account_name}' 的交易记录"}, ensure_ascii=False)

    summary = {
        "对手方": account_name,
        "交易笔数": len(df),
        "总收入": float(df["入账金额"].sum()),
        "总支出": float(df["出账金额"].sum()),
        "净额": float(df["入账金额"].sum() - df["出账金额"].sum()),
        "首次交易": df["交易日期"].min(),
        "末次交易": df["交易日期"].max(),
        "明细": df[["交易日期", "入账金额", "出账金额", "摘要", "交易流水号"]].to_dict(orient="records"),
    }

    return json.dumps(summary, ensure_ascii=False, default=str)
