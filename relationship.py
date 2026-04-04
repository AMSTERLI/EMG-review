"""
按样本量区间统计论文篇数，并分别统计各区间内性别、年龄、人种或肤色的报告率。

区间划分（整数样本量）：
- 小于等于 5
- 大于 5 且小于等于 15
- 大于 15 且小于等于 30
- 大于 30 且小于等于 60
- 大于 60 且小于等于 100
- 大于 100

无效或缺失的 Sample_Size 单独计入「无效或缺失」。

报告率口径与 source_stats 一致：字段经规范化后不等于「Not reported」视为已报告。

论文主题分类（默认列名 ``Assigned_Categories``）：可多标签，以英文逗号分隔（逗号后可跟任意空格），
例如 ``Clinical & Diagnostic, Neurophysiology``。同一篇论文属于多个类别时，各类别分别计数（``paper_count``
按「论文—类别」计，各类别下报告率分母为该类别所含论文篇数）。空或无效主题计为「（未标注主题）」。

主题 × 样本量热力图矩阵（全计数法）：多标签论文按类别「分身」计数；每格数值为
「该类别中落在该样本量区间的篇数 / 该类别总篇数 × 100%」，分母 N 为打上该类标签的论文总数（每篇多标签论文在各类各算 1）。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path("PDF_Dataset/Sampled_Papers_Stratified.csv")
DEFAULT_OUTPUT = Path("analysis_outputs/sample_size_bins.csv")
DEFAULT_TOPIC_OUTPUT = Path("analysis_outputs/topic_demographics_reporting_rates.csv")
DEFAULT_TOPIC_SAMPLE_BIN_MATRIX_OUTPUT = Path(
    "analysis_outputs/topic_category_sample_size_share_matrix.csv"
)
DEFAULT_TOPIC_COLUMN = "Assigned_Categories"
MISSING_LABEL = "无效或缺失"
TOPIC_UNLABELED = "（未标注主题）"
NOT_REPORTED = "Not reported"

DEMOGRAPHICS_COLUMNS = {
    "gender": "Gender_Details",
    "age": "Age_Details",
    "race_or_skin": "Race_Ethnicity_Details",
}

# 输出顺序：先六档样本量，最后缺失
BIN_LABELS_ORDER: list[str] = [
    "小于等于5",
    "大于5小于等于15",
    "大于15小于等于30",
    "大于30小于等于60",
    "大于60小于等于100",
    "大于100",
    MISSING_LABEL,
]


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return NOT_REPORTED
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text else NOT_REPORTED


def is_reported(value: object) -> bool:
    return normalize_text(value).casefold() != NOT_REPORTED.casefold()


def parse_sample_size(value: object) -> int | None:
    """与 demographics 抽取口径一致：可解析为整数则返回，否则 None。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        n = int(value)
        return n if n >= 0 else None

    text = str(value).strip()
    if not text or text.lower() == "null" or text.lower() == "not reported":
        return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    if not numeric.is_integer():
        return None
    n = int(numeric)
    return n if n >= 0 else None


def sample_size_to_bin_label(n: int) -> str:
    """将非负整数样本量映射到上述六档之一。"""
    if n <= 5:
        return "小于等于5"
    if n <= 15:
        return "大于5小于等于15"
    if n <= 30:
        return "大于15小于等于30"
    if n <= 60:
        return "大于30小于等于60"
    if n <= 100:
        return "大于60小于等于100"
    return "大于100"


def _validate_demographics_columns(frame: pd.DataFrame) -> None:
    missing = [c for c in DEMOGRAPHICS_COLUMNS.values() if c not in frame.columns]
    if missing:
        raise ValueError(f"缺少人口学列: {', '.join(missing)}")


def split_topic_categories(value: object) -> list[str]:
    """
    解析主题多标签：以逗号分隔，逗号后允许空格（与「逗号 + 空格」及单逗号写法兼容）。
    去重且保序；空则返回空列表。
    """
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.lower() == "null" or text.lower() == "not reported":
        return []
    parts = [p.strip() for p in re.split(r",\s*", text)]
    unique: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if not p or p in seen:
            continue
        seen.add(p)
        unique.append(p)
    return unique


def compute_topic_demographics_table(
    frame: pd.DataFrame,
    *,
    topic_column: str = DEFAULT_TOPIC_COLUMN,
) -> pd.DataFrame:
    """
    按主题类别统计人口学报告率。
    多标签论文在多个类别中各计 1 篇（paper_count 为属于该类别的论文数）。
    """
    _validate_demographics_columns(frame)
    if topic_column not in frame.columns:
        raise ValueError(f"缺少主题列: {topic_column}")

    gender_col = DEMOGRAPHICS_COLUMNS["gender"]
    age_col = DEMOGRAPHICS_COLUMNS["age"]
    race_col = DEMOGRAPHICS_COLUMNS["race_or_skin"]
    total_corpus = len(frame)

    expanded_rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        cats = split_topic_categories(row[topic_column])
        if not cats:
            cats = [TOPIC_UNLABELED]
        for cat in cats:
            expanded_rows.append(
                {
                    "_topic": cat,
                    gender_col: row[gender_col],
                    age_col: row[age_col],
                    race_col: row[race_col],
                }
            )

    long_df = pd.DataFrame(expanded_rows)
    rows: list[dict[str, object]] = []
    for topic, g in long_df.groupby("_topic", sort=False):
        n = len(g)
        gender_rep = int(g[gender_col].map(is_reported).sum())
        age_rep = int(g[age_col].map(is_reported).sum())
        race_rep = int(g[race_col].map(is_reported).sum())
        rows.append(
            {
                "topic_category": topic,
                "paper_count": n,
                "paper_share_of_corpus_pct": round((n / total_corpus) * 100, 2) if total_corpus else 0.0,
                "gender_reported_count": gender_rep,
                "gender_reporting_rate": round((gender_rep / n) * 100, 2) if n else 0.0,
                "age_reported_count": age_rep,
                "age_reporting_rate": round((age_rep / n) * 100, 2) if n else 0.0,
                "race_or_skin_reported_count": race_rep,
                "race_or_skin_reporting_rate": round((race_rep / n) * 100, 2) if n else 0.0,
            }
        )

    result = pd.DataFrame(rows)
    return result.sort_values(
        by=["paper_count", "topic_category"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def compute_topic_sample_size_share_matrix(
    frame: pd.DataFrame,
    *,
    topic_column: str = DEFAULT_TOPIC_COLUMN,
    sample_column: str = "Sample_Size",
) -> pd.DataFrame:
    """
    行 = 主题类别，列 = 样本量区间，格 = 占比（%）。

    全计数法：同一篇论文的每个标签各计一条；某格 = count(类别∩区间) / 该类别总条数 × 100。
    """
    if topic_column not in frame.columns:
        raise ValueError(f"缺少主题列: {topic_column}")

    work = add_sample_size_bin_column(frame, column=sample_column)
    records: list[dict[str, str]] = []
    for _, row in work.iterrows():
        cats = split_topic_categories(row[topic_column])
        if not cats:
            cats = [TOPIC_UNLABELED]
        bin_label = row["_sample_size_bin"]
        for cat in cats:
            records.append({"topic_category": cat, "sample_size_bin": bin_label})

    long_df = pd.DataFrame(records)
    if long_df.empty:
        empty = pd.DataFrame(columns=["topic_category", "category_n", *BIN_LABELS_ORDER])
        return empty

    count_table = long_df.groupby(["topic_category", "sample_size_bin"]).size().unstack(fill_value=0)
    count_table = count_table.reindex(columns=BIN_LABELS_ORDER, fill_value=0)

    n_per_category = long_df.groupby("topic_category").size()
    topics_order = n_per_category.sort_values(ascending=False).index

    out_rows: list[dict[str, object]] = []
    for topic in topics_order:
        n = int(n_per_category.loc[topic])
        row_dict: dict[str, object] = {
            "topic_category": topic,
            "category_n": n,
        }
        if topic in count_table.index:
            counts = count_table.loc[topic]
        else:
            counts = pd.Series(0, index=BIN_LABELS_ORDER)
        for b in BIN_LABELS_ORDER:
            c = int(counts[b]) if b in counts.index else 0
            row_dict[b] = round((c / n) * 100, 2) if n else 0.0
        out_rows.append(row_dict)

    return pd.DataFrame(out_rows)


def _write_topic_bin_matrix_csv(result: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = result.copy()
    for b in BIN_LABELS_ORDER:
        if b in out.columns:
            out[b] = out[b].map(lambda x: f"{float(x):.2f}")
    out.to_csv(output_path, index=False, encoding="utf-8-sig")


def add_sample_size_bin_column(
    frame: pd.DataFrame,
    *,
    column: str = "Sample_Size",
) -> pd.DataFrame:
    if column not in frame.columns:
        raise ValueError(f"缺少列: {column}")

    parsed = frame[column].map(parse_sample_size)
    labels: list[str] = []
    for v in parsed:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            labels.append(MISSING_LABEL)
        else:
            labels.append(sample_size_to_bin_label(int(v)))
    return frame.assign(_sample_size_bin=labels)


def compute_sample_size_bin_table(
    frame: pd.DataFrame,
    *,
    sample_column: str = "Sample_Size",
) -> pd.DataFrame:
    _validate_demographics_columns(frame)
    work = add_sample_size_bin_column(frame, column=sample_column)
    total_rows = len(work)

    rows: list[dict[str, object]] = []
    gender_col = DEMOGRAPHICS_COLUMNS["gender"]
    age_col = DEMOGRAPHICS_COLUMNS["age"]
    race_col = DEMOGRAPHICS_COLUMNS["race_or_skin"]

    for bin_label in BIN_LABELS_ORDER:
        g = work[work["_sample_size_bin"] == bin_label]
        n = len(g)
        gender_rep = int(g[gender_col].map(is_reported).sum()) if n else 0
        age_rep = int(g[age_col].map(is_reported).sum()) if n else 0
        race_rep = int(g[race_col].map(is_reported).sum()) if n else 0

        rows.append(
            {
                "sample_size_bin": bin_label,
                "paper_count": n,
                "paper_percentage": round((n / total_rows) * 100, 2) if total_rows else 0.0,
                "gender_reported_count": gender_rep,
                "gender_reporting_rate": round((gender_rep / n) * 100, 2) if n else 0.0,
                "age_reported_count": age_rep,
                "age_reporting_rate": round((age_rep / n) * 100, 2) if n else 0.0,
                "race_or_skin_reported_count": race_rep,
                "race_or_skin_reporting_rate": round((race_rep / n) * 100, 2) if n else 0.0,
            }
        )

    return pd.DataFrame(rows)


def _format_rate_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        out[col] = out[col].map(lambda x: f"{float(x):.2f}")
    return out


def _write_sample_size_csv(result: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = _format_rate_columns(
        result,
        (
            "paper_percentage",
            "gender_reporting_rate",
            "age_reporting_rate",
            "race_or_skin_reporting_rate",
        ),
    )
    out.to_csv(output_path, index=False, encoding="utf-8-sig")


def _write_topic_csv(result: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out = _format_rate_columns(
        result,
        (
            "paper_share_of_corpus_pct",
            "gender_reporting_rate",
            "age_reporting_rate",
            "race_or_skin_reporting_rate",
        ),
    )
    out.to_csv(output_path, index=False, encoding="utf-8-sig")


def run(
    csv_path: Path,
    output_path: Path | None,
    topic_output_path: Path | None,
    topic_bin_matrix_output_path: Path | None,
    *,
    column: str = "Sample_Size",
    topic_column: str = DEFAULT_TOPIC_COLUMN,
    skip_topic: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"未找到 CSV: {csv_path}")

    frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    result_bins = compute_sample_size_bin_table(frame, sample_column=column)

    if output_path is not None:
        _write_sample_size_csv(result_bins, Path(output_path))

    topic_result: pd.DataFrame | None = None
    topic_matrix: pd.DataFrame | None = None
    if not skip_topic:
        if topic_column not in frame.columns:
            print(f"警告: 未找到主题列「{topic_column}」，已跳过主题相关统计。")
        else:
            topic_result = compute_topic_demographics_table(frame, topic_column=topic_column)
            if topic_output_path is not None:
                _write_topic_csv(topic_result, Path(topic_output_path))

            topic_matrix = compute_topic_sample_size_share_matrix(
                frame, topic_column=topic_column, sample_column=column
            )
            if topic_bin_matrix_output_path is not None:
                _write_topic_bin_matrix_csv(topic_matrix, Path(topic_bin_matrix_output_path))

    return result_bins, topic_result, topic_matrix


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="按样本量区间统计篇数及性别、年龄、人种/肤色报告率；按论文主题类别统计人口学报告率。"
    )
    p.add_argument("--csv-path", type=Path, default=DEFAULT_CSV, help="采样表路径")
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="样本量区间统计 CSV（设为 none 则不写文件）",
    )
    p.add_argument(
        "--topic-output",
        type=Path,
        default=DEFAULT_TOPIC_OUTPUT,
        help="主题类别人口学报告率 CSV（设为 none 则不写；需存在主题列）",
    )
    p.add_argument(
        "--topic-bin-matrix-output",
        type=Path,
        default=DEFAULT_TOPIC_SAMPLE_BIN_MATRIX_OUTPUT,
        help="主题×样本量区间占比矩阵 CSV（全计数法，热力图用；设为 none 则不写）",
    )
    p.add_argument(
        "--topic-column",
        type=str,
        default=DEFAULT_TOPIC_COLUMN,
        help="主题多标签列名（逗号分隔，默认 Assigned_Categories）",
    )
    p.add_argument("--skip-topic", action="store_true", help="不统计主题类别报告率")
    p.add_argument("--column", type=str, default="Sample_Size", help="样本量列名")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    output = None if str(args.output).lower() == "none" else args.output
    topic_out = None if str(args.topic_output).lower() == "none" else args.topic_output
    topic_matrix_out = (
        None if str(args.topic_bin_matrix_output).lower() == "none" else args.topic_bin_matrix_output
    )
    result_bins, topic_result, topic_matrix = run(
        args.csv_path,
        output,
        topic_out,
        topic_matrix_out,
        column=args.column,
        topic_column=args.topic_column,
        skip_topic=args.skip_topic,
    )
    print(f"输入: {args.csv_path}")
    print(f"总记录数: {int(result_bins['paper_count'].sum())}")
    print("\n各样本量区间：篇数与报告率（占该区间篇数）")
    for _, row in result_bins.iterrows():
        print(
            f"  {row['sample_size_bin']}: "
            f"n={int(row['paper_count'])} ({row['paper_percentage']:.2f}% of all); "
            f"性别 {row['gender_reporting_rate']:.2f}% ({int(row['gender_reported_count'])}/{int(row['paper_count']) or '-'}); "
            f"年龄 {row['age_reporting_rate']:.2f}% ({int(row['age_reported_count'])}/{int(row['paper_count']) or '-'}); "
            f"人种/肤色 {row['race_or_skin_reporting_rate']:.2f}% ({int(row['race_or_skin_reported_count'])}/{int(row['paper_count']) or '-'})"
        )
    if output is not None:
        print(f"\n已写入样本量区间: {output}")

    if topic_result is not None:
        print("\n各主题类别：篇数（多标签可重复计篇）与报告率（占该类别篇数）")
        for _, row in topic_result.iterrows():
            print(
                f"  {row['topic_category']}: "
                f"n={int(row['paper_count'])} ({row['paper_share_of_corpus_pct']:.2f}% of corpus rows); "
                f"性别 {row['gender_reporting_rate']:.2f}%; "
                f"年龄 {row['age_reporting_rate']:.2f}%; "
                f"人种/肤色 {row['race_or_skin_reporting_rate']:.2f}%"
            )
        if topic_out is not None:
            print(f"\n已写入主题报告率: {topic_out}")

    if topic_matrix is not None:
        print(
            f"\n主题×样本量区间占比矩阵（每格=该类该区间篇数/该类总篇数）已生成，"
            f"共 {len(topic_matrix)} 行。"
        )
        if topic_matrix_out is not None:
            print(f"已写入: {topic_matrix_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
