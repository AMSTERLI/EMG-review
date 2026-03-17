import argparse
from pathlib import Path

import pandas as pd


DEFAULT_IEEE_FILE = Path("original-csv/ieee_emg_sampled_30_percent_2000_2026.csv")
DEFAULT_PUBMED_FILE = Path("original-csv/pubmed_sampled_30_percent_2000_2026.csv")
DEFAULT_OUTPUT_FILE = Path("original-csv/merged_sampled_ieee_pubmed_2000_2026.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge sampled IEEE and PubMed CSV files by year and label the database source."
    )
    parser.add_argument("--ieee-file", type=Path, default=DEFAULT_IEEE_FILE)
    parser.add_argument("--pubmed-file", type=Path, default=DEFAULT_PUBMED_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    return parser.parse_args()


def read_csv_with_fallbacks(csv_path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
        try:
            return pd.read_csv(csv_path, encoding=encoding, on_bad_lines="skip")
        except UnicodeDecodeError:
            continue
    return pd.read_csv(csv_path, on_bad_lines="skip")


def prepare_ieee_frame(frame: pd.DataFrame) -> pd.DataFrame:
    ieee_frame = frame.copy()
    ieee_frame["Year"] = pd.to_numeric(ieee_frame["Publication Year"], errors="coerce")
    doi_series = ieee_frame.get("DOI", pd.Series(index=ieee_frame.index, dtype="object"))
    doc_id_series = ieee_frame.get(
        "Document Identifier", pd.Series(index=ieee_frame.index, dtype="object")
    )
    normalized_id = doi_series.fillna("").astype(str).str.strip()
    fallback_id = doc_id_series.fillna("").astype(str).str.strip()
    normalized_id = normalized_id.mask(normalized_id == "", fallback_id)

    standardized_frame = pd.DataFrame(
        {
            "ID": normalized_id,
            "Title": ieee_frame.get(
                "Document Title", pd.Series(index=ieee_frame.index, dtype="object")
            ),
            "Abstract": ieee_frame.get(
                "Abstract", pd.Series(index=ieee_frame.index, dtype="object")
            ),
            "Database": "IEEE",
            "Year": ieee_frame["Year"],
        }
    )
    return standardized_frame


def prepare_pubmed_frame(frame: pd.DataFrame) -> pd.DataFrame:
    pubmed_frame = frame.copy()
    pubmed_frame["Year"] = pd.to_numeric(pubmed_frame["Year"], errors="coerce")
    standardized_frame = pd.DataFrame(
        {
            "ID": pubmed_frame.get("PMID", pd.Series(index=pubmed_frame.index, dtype="object")),
            "Title": pubmed_frame.get(
                "Title", pd.Series(index=pubmed_frame.index, dtype="object")
            ),
            "Abstract": pubmed_frame.get(
                "Abstract", pd.Series(index=pubmed_frame.index, dtype="object")
            ),
            "Database": "PubMed",
            "Year": pubmed_frame["Year"],
        }
    )
    return standardized_frame


def main() -> int:
    args = parse_args()

    ieee_frame = prepare_ieee_frame(read_csv_with_fallbacks(args.ieee_file))
    pubmed_frame = prepare_pubmed_frame(read_csv_with_fallbacks(args.pubmed_file))

    merged_frame = pd.concat([ieee_frame, pubmed_frame], ignore_index=True, sort=False)
    merged_frame["_year_sort"] = pd.to_numeric(merged_frame["Year"], errors="coerce")
    merged_frame.sort_values(by="_year_sort", kind="stable", inplace=True)
    merged_frame["Year"] = merged_frame["Year"].astype("Int64")
    merged_frame = merged_frame[["ID", "Title", "Abstract", "Year", "Database"]].copy()

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    merged_frame.to_csv(args.output_file, index=False, encoding="utf-8-sig")

    print(f"IEEE rows: {len(ieee_frame)}")
    print(f"PubMed rows: {len(pubmed_frame)}")
    print(f"Merged rows: {len(merged_frame)}")
    print(f"Output file: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
