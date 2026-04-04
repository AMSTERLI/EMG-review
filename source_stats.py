import argparse
import re
from pathlib import Path

import pandas as pd


DEFAULT_INPUT_CSV = Path("PDF_Dataset/Sampled_Papers_Stratified.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_outputs/source_stats")
NOT_REPORTED = "Not reported"
SOURCE_COLUMNS = {
    "database": "Database",
    "journal": "Journal",
    "country": "Country_of_Study",
}
DEMOGRAPHICS_COLUMNS = {
    "gender": "Gender_Details",
    "age": "Age_Details",
    "race_or_skin": "Race_Ethnicity_Details",
}
YEAR_COLUMN = "Year"

DATABASE_ALIASES = {
    "pubmed": "PubMed",
    "ieee": "IEEE",
    "ieee xplore": "IEEE Xplore",
}

COUNTRY_ALIASES = {
    "usa": "United States",
    "u.s.a.": "United States",
    "u.s.a": "United States",
    "us": "United States",
    "u.s.": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "u.k": "United Kingdom",
    "united kingdom": "United Kingdom",
}


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return NOT_REPORTED

    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text else NOT_REPORTED


def normalize_database(value: object) -> str:
    text = normalize_text(value)
    if text == NOT_REPORTED:
        return text

    return DATABASE_ALIASES.get(text.casefold(), text)


def normalize_journal(value: object) -> str:
    return normalize_text(value)


def normalize_country(value: object) -> str:
    text = normalize_text(value)
    if text == NOT_REPORTED:
        return text

    return COUNTRY_ALIASES.get(text.casefold(), text)


def build_counts_frame(
    frame: pd.DataFrame,
    column_name: str,
    normalizer,
) -> pd.DataFrame:
    normalized_series = frame[column_name].map(normalizer)
    counts = normalized_series.value_counts(dropna=False).rename_axis("value").reset_index(name="count")
    counts["percentage"] = ((counts["count"] / len(frame)) * 100).round(2)
    return counts.sort_values(by=["count", "value"], ascending=[False, True], kind="stable").reset_index(drop=True)


def _validate_columns(frame: pd.DataFrame) -> None:
    required_columns = [*SOURCE_COLUMNS.values(), *DEMOGRAPHICS_COLUMNS.values(), YEAR_COLUMN]
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Missing required columns: {missing}")


def _write_counts_csv(counts: pd.DataFrame, path: Path) -> None:
    output_frame = counts.copy()
    rate_columns = [column for column in output_frame.columns if column == "percentage" or column.endswith("_rate")]
    for column in rate_columns:
        output_frame[column] = output_frame[column].map(lambda value: f"{float(value):.2f}")
    output_frame.to_csv(path, index=False, encoding="utf-8-sig")


def format_top_values(counts: pd.DataFrame, *, top_n: int = 5) -> str:
    top_rows = counts.head(top_n).itertuples(index=False)
    return "; ".join(f"{row.value} ({row.count}, {row.percentage:.2f}%)" for row in top_rows)


def is_reported(value: object) -> bool:
    return normalize_text(value).casefold() != NOT_REPORTED.casefold()


def build_overall_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    total_count = len(frame)
    rows: list[dict[str, object]] = []
    metrics = [
        ("gender_reporting_rate", DEMOGRAPHICS_COLUMNS["gender"]),
        ("age_reporting_rate", DEMOGRAPHICS_COLUMNS["age"]),
        ("race_or_skin_reporting_rate", DEMOGRAPHICS_COLUMNS["race_or_skin"]),
    ]
    for metric_name, column_name in metrics:
        reported_count = int(frame[column_name].map(is_reported).sum())
        reporting_rate = 0.0 if total_count == 0 else round((reported_count / total_count) * 100, 2)
        rows.append(
            {
                "metric": metric_name,
                "reported_count": reported_count,
                "total_count": total_count,
                "reporting_rate": reporting_rate,
            }
        )
    return pd.DataFrame(rows)


def build_yearly_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["year"] = working[YEAR_COLUMN].map(normalize_text)

    rows: list[dict[str, object]] = []
    for year, group in working.groupby("year", dropna=False):
        total_count = len(group)
        gender_count = int(group[DEMOGRAPHICS_COLUMNS["gender"]].map(is_reported).sum())
        age_count = int(group[DEMOGRAPHICS_COLUMNS["age"]].map(is_reported).sum())
        race_count = int(group[DEMOGRAPHICS_COLUMNS["race_or_skin"]].map(is_reported).sum())
        rows.append(
            {
                "year": year,
                "total_count": total_count,
                "gender_reported_count": gender_count,
                "gender_reporting_rate": round((gender_count / total_count) * 100, 2) if total_count else 0.0,
                "age_reported_count": age_count,
                "age_reporting_rate": round((age_count / total_count) * 100, 2) if total_count else 0.0,
                "race_or_skin_reported_count": race_count,
                "race_or_skin_reporting_rate": round((race_count / total_count) * 100, 2) if total_count else 0.0,
            }
        )

    yearly = pd.DataFrame(rows)
    sort_year = pd.to_numeric(yearly["year"], errors="coerce")
    yearly = yearly.assign(_year_num=sort_year).sort_values(
        by=["_year_num", "year"], ascending=[True, True], na_position="last", kind="stable"
    )
    return yearly.drop(columns=["_year_num"]).reset_index(drop=True)


def build_database_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["database"] = working[SOURCE_COLUMNS["database"]].map(normalize_database)

    rows: list[dict[str, object]] = []
    for database, group in working.groupby("database", dropna=False):
        total_count = len(group)
        gender_count = int(group[DEMOGRAPHICS_COLUMNS["gender"]].map(is_reported).sum())
        age_count = int(group[DEMOGRAPHICS_COLUMNS["age"]].map(is_reported).sum())
        race_count = int(group[DEMOGRAPHICS_COLUMNS["race_or_skin"]].map(is_reported).sum())
        rows.append(
            {
                "database": database,
                "total_count": total_count,
                "gender_reported_count": gender_count,
                "gender_reporting_rate": round((gender_count / total_count) * 100, 2) if total_count else 0.0,
                "age_reported_count": age_count,
                "age_reporting_rate": round((age_count / total_count) * 100, 2) if total_count else 0.0,
                "race_or_skin_reported_count": race_count,
                "race_or_skin_reporting_rate": round((race_count / total_count) * 100, 2) if total_count else 0.0,
            }
        )

    database_rates = pd.DataFrame(rows)
    return database_rates.sort_values(
        by=["total_count", "database"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)


def build_database_yearly_reporting_rates(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["database"] = working[SOURCE_COLUMNS["database"]].map(normalize_database)
    working["year"] = working[YEAR_COLUMN].map(normalize_text)

    rows: list[dict[str, object]] = []
    for (database, year), group in working.groupby(["database", "year"], dropna=False):
        total_count = len(group)
        gender_count = int(group[DEMOGRAPHICS_COLUMNS["gender"]].map(is_reported).sum())
        age_count = int(group[DEMOGRAPHICS_COLUMNS["age"]].map(is_reported).sum())
        race_count = int(group[DEMOGRAPHICS_COLUMNS["race_or_skin"]].map(is_reported).sum())
        rows.append(
            {
                "database": database,
                "year": year,
                "total_count": total_count,
                "gender_reported_count": gender_count,
                "gender_reporting_rate": round((gender_count / total_count) * 100, 2) if total_count else 0.0,
                "age_reported_count": age_count,
                "age_reporting_rate": round((age_count / total_count) * 100, 2) if total_count else 0.0,
                "race_or_skin_reported_count": race_count,
                "race_or_skin_reporting_rate": round((race_count / total_count) * 100, 2) if total_count else 0.0,
            }
        )

    database_yearly = pd.DataFrame(rows)
    sort_year = pd.to_numeric(database_yearly["year"], errors="coerce")
    database_yearly = database_yearly.assign(_year_num=sort_year).sort_values(
        by=["total_count", "database", "_year_num", "year"],
        ascending=[False, True, True, True],
        na_position="last",
        kind="stable",
    )
    return database_yearly.drop(columns=["_year_num"]).reset_index(drop=True)


def write_source_statistics(*, csv_path: Path, output_dir: Path) -> dict[str, object]:
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    _validate_columns(frame)
    output_dir.mkdir(parents=True, exist_ok=True)

    database_counts = build_counts_frame(frame, SOURCE_COLUMNS["database"], normalize_database)
    journal_counts = build_counts_frame(frame, SOURCE_COLUMNS["journal"], normalize_journal)
    country_counts = build_counts_frame(frame, SOURCE_COLUMNS["country"], normalize_country)
    overall_rates = build_overall_reporting_rates(frame)
    yearly_rates = build_yearly_reporting_rates(frame)
    database_rates = build_database_reporting_rates(frame)
    database_yearly_rates = build_database_yearly_reporting_rates(frame)

    _write_counts_csv(database_counts, output_dir / "database_counts.csv")
    _write_counts_csv(journal_counts, output_dir / "journal_counts.csv")
    _write_counts_csv(country_counts, output_dir / "country_counts.csv")
    _write_counts_csv(overall_rates, output_dir / "overall_demographics_reporting_rates.csv")
    _write_counts_csv(yearly_rates, output_dir / "yearly_demographics_reporting_rates.csv")
    _write_counts_csv(database_rates, output_dir / "database_demographics_reporting_rates.csv")
    _write_counts_csv(
        database_yearly_rates, output_dir / "database_yearly_demographics_reporting_rates.csv"
    )

    return {
        "total_rows": len(frame),
        "database_unique_values": len(database_counts),
        "journal_unique_values": len(journal_counts),
        "country_unique_values": len(country_counts),
        "database_top_values": format_top_values(database_counts),
        "journal_top_values": format_top_values(journal_counts),
        "country_top_values": format_top_values(country_counts),
        "overall_gender_rate": overall_rates.iloc[0].to_dict(),
        "overall_age_rate": overall_rates.iloc[1].to_dict(),
        "overall_race_rate": overall_rates.iloc[2].to_dict(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count normalized database, journal, and country sources in the sampled papers CSV."
    )
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = write_source_statistics(csv_path=args.csv_path, output_dir=args.output_dir)
    print(f"Input CSV: {args.csv_path}")
    print(f"Total rows: {summary['total_rows']}")
    print(f"Database unique values: {summary['database_unique_values']}")
    print(f"Database top values: {summary['database_top_values']}")
    print(f"Journal unique values: {summary['journal_unique_values']}")
    print(f"Journal top values: {summary['journal_top_values']}")
    print(f"Country unique values: {summary['country_unique_values']}")
    print(f"Country top values: {summary['country_top_values']}")
    print(
        "Overall gender reporting rate: "
        f"{summary['overall_gender_rate']['reporting_rate']:.2f}% "
        f"({int(summary['overall_gender_rate']['reported_count'])}/{int(summary['overall_gender_rate']['total_count'])})"
    )
    print(
        "Overall age reporting rate: "
        f"{summary['overall_age_rate']['reporting_rate']:.2f}% "
        f"({int(summary['overall_age_rate']['reported_count'])}/{int(summary['overall_age_rate']['total_count'])})"
    )
    print(
        "Overall race/skin reporting rate: "
        f"{summary['overall_race_rate']['reporting_rate']:.2f}% "
        f"({int(summary['overall_race_rate']['reported_count'])}/{int(summary['overall_race_rate']['total_count'])})"
    )
    print("Database reporting files: database_demographics_reporting_rates.csv")
    print("Database-year reporting files: database_yearly_demographics_reporting_rates.csv")
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
