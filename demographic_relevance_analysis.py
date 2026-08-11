import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency should exist in real runs
    OpenAI = None

from source_stats import (
    DEMOGRAPHICS_COLUMNS,
    build_overall_reporting_rates,
    is_reported,
)


DEFAULT_INPUT_CSV = Path("PDF_Dataset/Sampled_Papers_Stratified.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_outputs/demographic_relevance")
DEFAULT_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-pro")
DEFAULT_SAVE_INTERVAL = 10
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 8.0
DEFAULT_POST_SUCCESS_DELAY = 0.4

CLASSIFICATION_COLUMNS = (
    "demographic_relevance",
    "demographic_relevance_label",
    "demographic_relevance_rationale",
    "demographic_relevance_variables",
)

LABELS = {
    0: "Demographic variables not part of the research question",
    1: "Demographic variables used as eligibility or control factors",
    2: "Sex/gender, age, race/ethnicity, skin phenotype, or related physiological differences are primary exposures or comparison factors",
}


@dataclass
class ClassificationStats:
    total_rows: int
    skipped_existing_count: int = 0
    success_count: int = 0
    api_error_count: int = 0


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def build_client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("The 'openai' package is not installed.")

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set DEEPSEEK_API_KEY or OPENAI_API_KEY before running this script.")

    return OpenAI(api_key=api_key, base_url=DEFAULT_BASE_URL)


def ensure_classification_columns(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in CLASSIFICATION_COLUMNS:
        if column not in working.columns:
            working[column] = ""
        working[column] = working[column].astype("object")
    return working


def create_classification_prompt(title: str, abstract: str) -> str:
    return f"""Classify the study purpose for a methodological survey of surface EMG papers.

Use this exact coding scheme:
0 = Demographic variables are not part of the research question.
1 = Demographic variables are used only as eligibility criteria, inclusion/exclusion restrictions, matching, adjustment, stratification, or control variables.
2 = sex/gender, age, race/ethnicity, skin phenotype/color/tone, or related physiological differences are primary exposures, primary comparison factors, or central study objectives.

Important rules:
- Assign 2 only when the title or abstract explicitly makes a demographic/skin/physiological difference a main comparison or exposure, such as male vs female, young vs older, children vs adults, aging, ethnicity/race, skin tone/type, or sex-specific/age-specific effects.
- Assign 1 when participants are limited by age or sex but those variables are not the central research question.
- Assign 0 when demographics are merely described or absent.
- Do not infer from author country, journal, or sample composition.

Return strict JSON with these keys:
{{
  "demographic_relevance": 0,
  "variables": ["sex/gender", "age", "race/ethnicity", "skin phenotype", "related physiology"],
  "rationale": "One concise sentence explaining the decision."
}}

Title: {title}

Abstract: {abstract}
"""


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def classify_row_with_llm(
    *,
    title: str,
    abstract: str,
    client: OpenAI | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, object]:
    llm_client = client or build_client()
    prompt = create_classification_prompt(title, abstract[:6000])
    response = llm_client.chat.completions.create(
        model=model_name,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a careful systematic-review classifier. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    parsed = _parse_json_content(content)
    relevance = int(parsed.get("demographic_relevance"))
    if relevance not in LABELS:
        raise ValueError(f"Invalid demographic_relevance value: {relevance}")

    variables = parsed.get("variables", [])
    if isinstance(variables, str):
        variables_text = variables
    else:
        variables_text = "; ".join(str(item) for item in variables)

    return {
        "demographic_relevance": str(relevance),
        "demographic_relevance_label": LABELS[relevance],
        "demographic_relevance_rationale": normalize_text(parsed.get("rationale")),
        "demographic_relevance_variables": variables_text,
    }


def classify_demographic_relevance(
    *,
    csv_path: Path,
    output_csv: Path,
    save_interval: int = DEFAULT_SAVE_INTERVAL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    post_success_delay: float = DEFAULT_POST_SUCCESS_DELAY,
    model_name: str = DEFAULT_MODEL_NAME,
    client: OpenAI | None = None,
    limit: int | None = None,
) -> ClassificationStats:
    csv_path = Path(csv_path)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if output_csv.exists():
        frame = ensure_classification_columns(pd.read_csv(output_csv, encoding="utf-8-sig"))
    else:
        frame = ensure_classification_columns(pd.read_csv(csv_path, encoding="utf-8-sig"))

    stats = ClassificationStats(total_rows=len(frame))
    llm_client = client or build_client()
    changes_since_save = 0

    processed_this_run = 0
    for row_index, row in frame.iterrows():
        if limit is not None and processed_this_run >= limit:
            break

        existing_value = normalize_text(row.get("demographic_relevance"))
        if existing_value in {"0", "1", "2"}:
            stats.skipped_existing_count += 1
            continue

        title = normalize_text(row.get("Title"))
        abstract = normalize_text(row.get("Abstract"))
        last_error = ""
        for attempt in range(max_retries):
            try:
                result = classify_row_with_llm(
                    title=title,
                    abstract=abstract,
                    client=llm_client,
                    model_name=model_name,
                )
                for column, value in result.items():
                    frame.at[row_index, column] = value
                stats.success_count += 1
                processed_this_run += 1
                changes_since_save += 1
                time.sleep(post_success_delay)
                break
            except Exception as exc:  # pragma: no cover - network/provider dependent
                last_error = str(exc)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        else:
            frame.at[row_index, "demographic_relevance_rationale"] = f"api_error: {last_error}"
            stats.api_error_count += 1
            processed_this_run += 1
            changes_since_save += 1

        if changes_since_save >= save_interval:
            frame.to_csv(output_csv, index=False, encoding="utf-8-sig")
            changes_since_save = 0

    frame.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return stats


def summarize_relevance(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["demographic_relevance"] = pd.to_numeric(working["demographic_relevance"], errors="coerce")
    rows: list[dict[str, object]] = []
    total_count = len(working)
    for relevance, count in working["demographic_relevance"].value_counts(dropna=False).sort_index().items():
        if pd.isna(relevance):
            label = "Unclassified"
            relevance_value = ""
        else:
            relevance_value = int(relevance)
            label = LABELS[relevance_value]
        rows.append(
            {
                "demographic_relevance": relevance_value,
                "label": label,
                "count": int(count),
                "percentage": round((int(count) / total_count) * 100, 2) if total_count else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_exclusion_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["demographic_relevance"] = pd.to_numeric(working["demographic_relevance"], errors="coerce")
    kept = working[working["demographic_relevance"] != 2].copy()
    excluded = working[working["demographic_relevance"] == 2].copy()

    overall = build_overall_reporting_rates(working)
    sensitivity = build_overall_reporting_rates(kept)
    rows: list[dict[str, object]] = []
    for _, overall_row in overall.iterrows():
        metric = overall_row["metric"]
        sensitivity_row = sensitivity[sensitivity["metric"] == metric].iloc[0]
        rows.append(
            {
                "metric": metric,
                "original_reported_count": int(overall_row["reported_count"]),
                "original_total_count": int(overall_row["total_count"]),
                "original_reporting_rate": float(overall_row["reporting_rate"]),
                "excluded_class_2_count": len(excluded),
                "sensitivity_reported_count": int(sensitivity_row["reported_count"]),
                "sensitivity_total_count": int(sensitivity_row["total_count"]),
                "sensitivity_reporting_rate": float(sensitivity_row["reporting_rate"]),
                "absolute_rate_change": round(
                    float(sensitivity_row["reporting_rate"]) - float(overall_row["reporting_rate"]), 2
                ),
            }
        )
    return pd.DataFrame(rows)


def build_excluded_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["demographic_relevance"] = pd.to_numeric(working["demographic_relevance"], errors="coerce")
    excluded = working[working["demographic_relevance"] == 2].copy()
    if excluded.empty:
        return pd.DataFrame(
            columns=[
                "metric",
                "reported_count",
                "total_count",
                "reporting_rate",
            ]
        )
    return build_overall_reporting_rates(excluded)


def write_category_article_lists(frame: pd.DataFrame, output_dir: Path) -> list[Path]:
    working = frame.copy()
    working["demographic_relevance"] = pd.to_numeric(working["demographic_relevance"], errors="coerce")

    preferred_columns = [
        "ID",
        "Title",
        "Year",
        "Database",
        "Journal",
        "demographic_relevance",
        "demographic_relevance_label",
        "demographic_relevance_variables",
        "demographic_relevance_rationale",
    ]
    columns = [column for column in preferred_columns if column in working.columns]

    paths: list[Path] = []
    for relevance in (0, 1, 2):
        subset = working[working["demographic_relevance"] == relevance].copy()
        output_path = output_dir / f"demographic_relevance_{relevance}_articles.csv"
        subset[columns].to_csv(output_path, index=False, encoding="utf-8-sig")
        paths.append(output_path)
    return paths


def write_analysis_outputs(*, classified_csv: Path, output_dir: Path) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(classified_csv, encoding="utf-8-sig")

    missing_columns = [column for column in DEMOGRAPHICS_COLUMNS.values() if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required demographic columns: {', '.join(missing_columns)}")

    summary = summarize_relevance(frame)
    sensitivity = build_exclusion_reporting_rates(frame)
    excluded_rates = build_excluded_reporting_rates(frame)
    category_paths = write_category_article_lists(frame, output_dir)

    summary.to_csv(output_dir / "demographic_relevance_counts.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(
        output_dir / "reporting_rates_excluding_demographic_relevance_2.csv",
        index=False,
        encoding="utf-8-sig",
    )
    excluded_rates.to_csv(
        output_dir / "reporting_rates_demographic_relevance_2_only.csv",
        index=False,
        encoding="utf-8-sig",
    )

    class_2_count = int((pd.to_numeric(frame["demographic_relevance"], errors="coerce") == 2).sum())
    return {
        "total_rows": len(frame),
        "class_2_count": class_2_count,
        "kept_after_excluding_class_2": len(frame) - class_2_count,
        "summary_path": output_dir / "demographic_relevance_counts.csv",
        "sensitivity_path": output_dir / "reporting_rates_excluding_demographic_relevance_2.csv",
        "category_paths": category_paths,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify demographic relevance and recompute reporting rates after excluding class 2 papers."
    )
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--classified-csv", type=Path)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--skip-classification", action="store_true")
    parser.add_argument("--save-interval", type=int, default=DEFAULT_SAVE_INTERVAL)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY)
    parser.add_argument("--post-success-delay", type=float, default=DEFAULT_POST_SUCCESS_DELAY)
    parser.add_argument("--limit", type=int, help="Classify at most this many unclassified rows in this run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    classified_csv = args.classified_csv or args.output_dir / "sampled_papers_with_demographic_relevance.csv"

    if not args.skip_classification:
        stats = classify_demographic_relevance(
            csv_path=args.csv_path,
            output_csv=classified_csv,
            save_interval=args.save_interval,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            post_success_delay=args.post_success_delay,
            model_name=args.model_name,
            limit=args.limit,
        )
        print(f"Classified rows: {stats.success_count}")
        print(f"Skipped existing rows: {stats.skipped_existing_count}")
        print(f"API error rows: {stats.api_error_count}")

    summary = write_analysis_outputs(classified_csv=classified_csv, output_dir=args.output_dir)
    print(f"Total rows: {summary['total_rows']}")
    print(f"Class 2 excluded rows: {summary['class_2_count']}")
    print(f"Rows retained after excluding class 2: {summary['kept_after_excluding_class_2']}")
    print(f"Classification counts: {summary['summary_path']}")
    print(f"Sensitivity reporting rates: {summary['sensitivity_path']}")
    print("Category article lists:")
    for path in summary["category_paths"]:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
