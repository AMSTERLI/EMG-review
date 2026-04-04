"""
人口学「是否报告」字段的卡方检验与趋势检验。

1. 两个数据库（PubMed / IEEE）× 各二分类报告结果：Pearson 卡方独立性检验（2×2）。
2. 有序样本量区间 × 各二分类报告结果：Cochran–Armitage 趋势检验（线性得分 0,1,…,k-1）。
3. 多主题类别（Domain，多标签全计数展开）× 各二分类报告结果：Pearson 卡方独立性检验（r×2）。

说明：多标签展开后，同一论文可对应多行，观测单元非严格独立，第 3 类结果宜作探索性解释。
"""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd
from scipy import stats

import relationship as rel

DEFAULT_CSV = Path("PDF_Dataset/Sampled_Papers_Stratified.csv")
DEFAULT_OUTPUT = Path("analysis_outputs/chi_square_demographics_tests.txt")

DATABASE_ALIASES = {
    "pubmed": "PubMed",
    "ieee": "IEEE",
    "ieee xplore": "IEEE Xplore",
}

OUTCOME_DEFS: list[tuple[str, str]] = [
    ("性别报告", rel.DEMOGRAPHICS_COLUMNS["gender"]),
    ("年龄报告", rel.DEMOGRAPHICS_COLUMNS["age"]),
    ("人种或肤色报告", rel.DEMOGRAPHICS_COLUMNS["race_or_skin"]),
]

# 趋势检验仅使用有序样本量档（不含「无效或缺失」）
TREND_BIN_LABELS: list[str] = [b for b in rel.BIN_LABELS_ORDER if b != rel.MISSING_LABEL]


def normalize_database(value: object) -> str:
    text = rel.normalize_text(value)
    if text == rel.NOT_REPORTED:
        return text
    t = DATABASE_ALIASES.get(text.casefold(), text)
    if t == "IEEE Xplore":
        return "IEEE"
    return t


def prepare_frame(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    for _, col in OUTCOME_DEFS:
        if col not in df.columns:
            raise ValueError(f"缺少列: {col}")
    if "Database" not in df.columns:
        raise ValueError("缺少列: Database")
    if "Sample_Size" not in df.columns:
        raise ValueError("缺少列: Sample_Size")

    out = df.copy()
    out["_db"] = out["Database"].map(normalize_database)
    for label, col in OUTCOME_DEFS:
        out[f"_rep_{col}"] = out[col].map(rel.is_reported)

    parsed = out["Sample_Size"].map(rel.parse_sample_size)
    bin_labels: list[str] = []
    for v in parsed:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            bin_labels.append(rel.MISSING_LABEL)
        else:
            bin_labels.append(rel.sample_size_to_bin_label(int(v)))
    out["_sample_bin"] = bin_labels
    return out


def chi2_database_vs_outcome(df: pd.DataFrame, outcome_col: str, outcome_name: str) -> str:
    sub = df[df["_db"].isin(["PubMed", "IEEE"])].copy()
    if len(sub) < 2:
        return f"【{outcome_name}】有效数据库样本不足，跳过。\n"

    obs = pd.crosstab(sub["_db"], sub[f"_rep_{outcome_col}"], dropna=False)
    # 列：False / True；保证 2×2
    for c in [False, True]:
        if c not in obs.columns:
            obs[c] = 0
    obs = obs.reindex(columns=[False, True], fill_value=0)
    obs = obs.reindex(index=["IEEE", "PubMed"], fill_value=0)

    chi2, p, dof, expected = stats.chi2_contingency(obs.values, correction=False)
    lines = [
        f"【{outcome_name}】数据库 x 是否报告（全样本 {len(sub)} 篇，仅 PubMed / IEEE）",
        "观测频数（行=数据库，列=[未报告, 已报告]）:",
        obs.to_string(),
        f"Pearson Chi-square = {chi2:.6f}, df = {dof}, p = {p:.6g}",
        f"期望频数最小值 = {expected.min():.4f}",
        "",
    ]
    return "\n".join(lines)


def cochran_armitage_trend(
    a: np.ndarray,
    n: np.ndarray,
    scores: np.ndarray | None = None,
) -> tuple[float, float]:
    """
    Cochran-Armitage 趋势检验（有序组 x 二分类）。
    a[i] = 第 i 组「成功」（已报告）人数，n[i] = 第 i 组总人数。
    scores: 单调得分，默认 0..k-1。
    返回 (Z, 双侧渐近 p)。
    """
    a = np.asarray(a, dtype=float)
    n = np.asarray(n, dtype=float)
    k = len(n)
    if scores is None:
        x = np.arange(k, dtype=float)
    else:
        x = np.asarray(scores, dtype=float)
    N = float(n.sum())
    if N <= 1:
        return float("nan"), float("nan")
    p_hat = float(a.sum() / N)
    if p_hat <= 0 or p_hat >= 1:
        return float("nan"), float("nan")
    num = float(np.dot(a, x) - p_hat * np.dot(n, x))
    denom_inner = float(np.dot(n, x**2) - (np.dot(n, x) ** 2) / N)
    if denom_inner <= 0:
        return float("nan"), float("nan")
    var = p_hat * (1 - p_hat) * denom_inner * (N - 1) / N
    if var <= 0:
        return float("nan"), float("nan")
    z = num / np.sqrt(var)
    p_two = 2.0 * stats.norm.sf(abs(z))
    return float(z), float(p_two)


def trend_sample_bin_vs_outcome(df: pd.DataFrame, outcome_col: str, outcome_name: str) -> str:
    sub = df[df["_sample_bin"].isin(TREND_BIN_LABELS)].copy()
    lines = [
        f"【{outcome_name}】样本量区间（有序）x 是否报告 - Cochran-Armitage 趋势检验",
        f"纳入篇数（样本量可分区间的记录）: {len(sub)}",
        "",
    ]
    rows = []
    for b in TREND_BIN_LABELS:
        g = sub[sub["_sample_bin"] == b]
        n_i = len(g)
        a_i = int(g[f"_rep_{outcome_col}"].sum()) if n_i else 0
        rows.append((b, n_i, a_i, n_i - a_i))
    table = pd.DataFrame(rows, columns=["样本量区间", "n", "已报告", "未报告"])
    lines.append(table.to_string(index=False))
    lines.append("")

    a = table["已报告"].to_numpy(dtype=float)
    n = table["n"].to_numpy(dtype=float)
    z, p = cochran_armitage_trend(a, n)
    lines.append(f"线性得分: {list(range(len(TREND_BIN_LABELS)))}（对应上表自上而下）")
    lines.append(f"Z = {z:.6f}, 双侧 p = {p:.6g}")
    lines.append("")
    return "\n".join(lines)


def expand_domain_rows(df: pd.DataFrame) -> pd.DataFrame:
    """多标签全计数展开；无标签者记为「（未标注主题）」。"""
    records: list[dict[str, object]] = []
    topic_col = rel.DEFAULT_TOPIC_COLUMN
    if topic_col not in df.columns:
        raise ValueError(f"缺少主题列 {topic_col}，无法进行 Domain 卡方检验。")

    for _, row in df.iterrows():
        cats = rel.split_topic_categories(row[topic_col])
        if not cats:
            cats = [rel.TOPIC_UNLABELED]
        for dom in cats:
            rec = {"_domain": dom}
            for label, col in OUTCOME_DEFS:
                rec[f"_rep_{col}"] = row[f"_rep_{col}"]
            records.append(rec)
    return pd.DataFrame(records)


def chi2_domain_vs_outcome(long_df: pd.DataFrame, outcome_col: str, outcome_name: str) -> str:
    obs = pd.crosstab(long_df["_domain"], long_df[f"_rep_{outcome_col}"], dropna=False)
    for c in [False, True]:
        if c not in obs.columns:
            obs[c] = 0
    obs = obs.reindex(columns=[False, True], fill_value=0)

    chi2, p, dof, expected = stats.chi2_contingency(obs.values, correction=False)
    lines = [
        f"【{outcome_name}】Domain（主题类别，多标签展开）x 是否报告",
        f"展开后行数（论文-类别对）: {len(long_df)}，Domain 类数: {obs.shape[0]}",
        "观测频数（行=Domain，列=[未报告, 已报告]）:",
        obs.to_string(),
        f"Pearson Chi-square = {chi2:.6f}, df = {dof}, p = {p:.6g}",
        f"期望频数最小值 = {expected.min():.4f}",
        "",
    ]
    return "\n".join(lines)


def run_all(csv_path: Path) -> str:
    df = prepare_frame(csv_path)
    buf = StringIO()
    w = buf.write

    w(dedent("""
    ======================================================================
    人口学报告 - 卡方检验与 Cochran-Armitage 趋势检验
    ======================================================================
    数据文件: 
    """).strip() + f" {csv_path}\n")
    w(f"总记录数: {len(df)}\n\n")

    w("-" * 70 + "\n")
    w("一、两个数据库（PubMed vs IEEE）x 是否报告 - Pearson Chi-square 独立性检验\n")
    w("-" * 70 + "\n\n")
    for name, col in OUTCOME_DEFS:
        w(chi2_database_vs_outcome(df, col, name))

    w("-" * 70 + "\n")
    w("二、有序样本量区间 x 是否报告 - Cochran-Armitage 趋势检验\n")
    w("-" * 70 + "\n\n")
    for name, col in OUTCOME_DEFS:
        w(trend_sample_bin_vs_outcome(df, col, name))

    w("-" * 70 + "\n")
    w("三、多个 Domain（主题）x 是否报告 - Pearson Chi-square 独立性检验（r x 2）\n")
    w("-" * 70 + "\n\n")
    long_df = expand_domain_rows(df)
    for name, col in OUTCOME_DEFS:
        w(chi2_domain_vs_outcome(long_df, col, name))

    w(dedent("""
    【方法说明】
    - 检验 1、3 使用 scipy.stats.chi2_contingency（无连续性校正）。
    - 检验 2 使用 Cochran-Armitage 线性趋势检验，得分与 relationship.py 中样本量区间顺序一致。
    - 期望频数过小时，渐近 p 值可能偏差；可考虑 Fisher 精确检验或合并类别。
    - 检验 3 对多标签论文按类别展开，行间不独立，解释需谨慎。
    ======================================================================
    """).strip() + "\n")

    return buf.getvalue()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="数据库/样本量区间/Domain 与报告情况的卡方及趋势检验。")
    p.add_argument("--csv-path", type=Path, default=DEFAULT_CSV)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--no-save", action="store_true", help="仅打印，不写文件")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    text = run_all(Path(args.csv_path))
    if not args.no_save:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, flush=True)
    if not args.no_save:
        print(f"\n已写入: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
