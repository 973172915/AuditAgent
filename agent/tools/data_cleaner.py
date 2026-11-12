"""数据清洗工具：处理脏数据的通用函数。"""
import re
from decimal import Decimal, InvalidOperation

import pandas as pd


def clean_amount(value) -> Decimal:
    """清洗金额字段：处理千分位逗号、货币符号、空值。

    Examples:
        "1,200.00" -> Decimal("1200.00")
        "¥3,500"   -> Decimal("3500")
        ""         -> Decimal("0")
    """
    if pd.isna(value) or value == "":
        return Decimal("0")

    s = str(value).strip()
    # 去掉货币符号和空格
    s = re.sub(r"[¥$€£\s]", "", s)
    # 去掉千分位逗号
    s = s.replace(",", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def clean_date(value, formats: list[str] | None = None) -> str:
    """清洗日期字段：统一为 YYYY-MM-DD 格式。

    支持的输入格式：
        2024-09-01, 2024/09/01, 20240901, 2024年9月1日
    """
    from datetime import datetime

    if pd.isna(value):
        return ""

    s = str(value).strip()

    # 中文日期
    cn_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", s)
    if cn_match:
        y, m, d = cn_match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # 标准格式尝试
    formats = formats or ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return s  # 无法解析时原样返回


def deduplicate(df: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """去重：基于指定列（默认全列）去除完全重复的行。"""
    if subset:
        before = len(df)
        df = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
        after = len(df)
        if before > after:
            print(f"[数据清洗] 去除 {before - after} 条重复记录")
    else:
        df = df.drop_duplicates().reset_index(drop=True)
    return df


def standardize_bank_statement(df: pd.DataFrame) -> pd.DataFrame:
    """标准化银行流水表。

    处理：
    - 金额字段的千分位和类型转换
    - 日期格式统一
    - 计算净额（入账 - 出账）
    """
    df = df.copy()

    if "入账金额" in df.columns:
        df["入账金额"] = df["入账金额"].apply(clean_amount).astype(float)
    if "出账金额" in df.columns:
        df["出账金额"] = df["出账金额"].apply(clean_amount).astype(float)
    if "余额" in df.columns:
        df["余额"] = df["余额"].apply(clean_amount).astype(float)

    if "交易日期" in df.columns:
        df["交易日期"] = df["交易日期"].apply(clean_date)

    # 计算净流入
    if "入账金额" in df.columns and "出账金额" in df.columns:
        df["净额"] = df["入账金额"] - df["出账金额"]

    return df


def standardize_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """标准化财务账簿表。"""
    df = df.copy()

    if "借方金额" in df.columns:
        df["借方金额"] = df["借方金额"].apply(clean_amount).astype(float)
    if "贷方金额" in df.columns:
        df["贷方金额"] = df["贷方金额"].apply(clean_amount).astype(float)

    if "记账日期" in df.columns:
        df["记账日期"] = df["记账日期"].apply(clean_date)

    return df
