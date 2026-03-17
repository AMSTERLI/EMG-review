import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import fitz
import pandas as pd
from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency should exist in real runs
    OpenAI = None


DEFAULT_INPUT_FILE = Path("PDF_Dataset/Sampled_Papers_Stratified.csv")
DEFAULT_PDF_FOLDER = Path("PDF_Dataset")
DEFAULT_MODEL_NAME = os.getenv("SCREENING_MODEL_NAME", "gemini-2.5-pro-cli")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.ttk.homes/v1")
DEFAULT_YEAR_START = 2000
DEFAULT_YEAR_END = 2026
DEFAULT_SAVE_INTERVAL = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 5.0
DEFAULT_POST_SUCCESS_DELAY = 2.0

ALLOWED_SCREENING_RESULTS = {
    "include",
    "exclude",
    "uncertain",
    "pdf_missing",
    "pdf_read_error",
    "api_error",
}


@dataclass
class ScreeningStats:
    total_rows: int
    skipped_existing_count: int = 0
    excluded_by_year_count: int = 0
    pdf_missing_count: int = 0
    pdf_read_error_count: int = 0
    success_count: int = 0
    api_error_count: int = 0


def build_client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("The 'openai' package is not installed.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    return OpenAI(api_key=api_key, base_url=DEFAULT_BASE_URL)


def normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_screening_result(value: object) -> str:
    normalized = normalize_text(value).lower()
    if normalized in ALLOWED_SCREENING_RESULTS:
        return normalized
    return "uncertain" if normalized else ""


def parse_year(value: object) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def ensure_screening_columns(frame: pd.DataFrame) -> pd.DataFrame:
    working_frame = frame.copy()
    for column in ("Screening_Result", "Screening_Reason"):
        if column not in working_frame.columns:
            working_frame[column] = ""
    return working_frame


def save_screening_csv(frame: pd.DataFrame, csv_path: Path) -> None:
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        document = fitz.open(pdf_path)
        text_parts: list[str] = []
        for page in document:
            text_parts.append(page.get_text("text"))
        document.close()
        return "\n".join(text_parts)
    except Exception as exc:
        return f"Error reading PDF: {exc}"


def create_screening_prompt(title: str, full_text: str, year_start: int, year_end: int) -> str:
    return f"""You are an expert reviewer screening full-text EMG studies for a systematic review.

Apply the following inclusion criteria. The paper must satisfy all of them:
1. Primary empirical research with original data.
2. Human participants only.
3. EMG (sEMG or iEMG) is a core data collection modality.
4. Publication year is within {year_start}-{year_end}.
5. Peer-reviewed English article.

Exclude the paper if any of the following apply:
- Review, meta-analysis, editorial, letter, or abstract-only publication.
- Animal or ex-vivo study.
- Pure simulation or only public dataset reuse without new human data collection.
- EMG mentioned only as a minor auxiliary method with no substantive EMG methods/results.

Paper Title: {title}
---
Full Text:
{full_text}
---

Return strict JSON only:
{{
  "screening_result": "include | exclude | uncertain",
  "screening_reason": "One concise sentence explaining the decision.",
  "study_design": "Short phrase",
  "population": "Short phrase",
  "emg_modality": "Short phrase",
  "language": "English | Non-English | Unclear",
  "year_check": "within_range | outside_range | unclear"
}}"""


def screen_pdf_with_llm(
    title: str,
    full_text: str,
    *,
    client=None,
    model_name: str = DEFAULT_MODEL_NAME,
    year_start: int = DEFAULT_YEAR_START,
    year_end: int = DEFAULT_YEAR_END,
) -> dict[str, str]:
    llm_client = client or build_client()
    prompt = create_screening_prompt(title, full_text[:100000], year_start, year_end)
    response = llm_client.chat.completions.create(
        model=model_name,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant designed to output strict JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content
    parsed = json.loads(content)
    return {
        "screening_result": normalize_screening_result(parsed.get("screening_result")) or "uncertain",
        "screening_reason": normalize_text(parsed.get("screening_reason")),
    }


def process_screening_csv(
    *,
    csv_path: Path,
    pdf_folder: Path,
    year_start: int = DEFAULT_YEAR_START,
    year_end: int = DEFAULT_YEAR_END,
    save_interval: int = DEFAULT_SAVE_INTERVAL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    post_success_delay: float = DEFAULT_POST_SUCCESS_DELAY,
    client=None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> ScreeningStats:
    csv_path = Path(csv_path)
    pdf_folder = Path(pdf_folder)

    frame = ensure_screening_columns(pd.read_csv(csv_path, encoding="utf-8-sig"))
    stats = ScreeningStats(total_rows=len(frame))
    changes_since_save = 0

    for row_index, row in tqdm(frame.iterrows(), total=len(frame), desc="Screening PDFs"):
        if normalize_text(row.get("Screening_Result")):
            stats.skipped_existing_count += 1
            continue

        publication_year = parse_year(row.get("Year"))
        if publication_year is not None and not (year_start <= publication_year <= year_end):
            frame.at[row_index, "Screening_Result"] = "exclude"
            frame.at[row_index, "Screening_Reason"] = f"Published outside {year_start}-{year_end}"
            stats.excluded_by_year_count += 1
            changes_since_save += 1
        else:
            doc_id = normalize_text(row.get("ID", row_index))
            safe_doc_id = doc_id.replace("/", "_")
            pdf_path = pdf_folder / f"{safe_doc_id}.pdf"

            if not pdf_path.exists():
                frame.at[row_index, "Screening_Result"] = "pdf_missing"
                frame.at[row_index, "Screening_Reason"] = "PDF file not found"
                stats.pdf_missing_count += 1
                changes_since_save += 1
            else:
                full_text = extract_text_from_pdf(pdf_path)
                if full_text.startswith("Error"):
                    frame.at[row_index, "Screening_Result"] = "pdf_read_error"
                    frame.at[row_index, "Screening_Reason"] = full_text
                    stats.pdf_read_error_count += 1
                    changes_since_save += 1
                else:
                    title = normalize_text(row.get("Title"))
                    last_error = ""
                    for attempt in range(max_retries):
                        try:
                            result = screen_pdf_with_llm(
                                title,
                                full_text,
                                client=client,
                                model_name=model_name,
                                year_start=year_start,
                                year_end=year_end,
                            )
                            frame.at[row_index, "Screening_Result"] = (
                                normalize_screening_result(result.get("screening_result")) or "uncertain"
                            )
                            frame.at[row_index, "Screening_Reason"] = (
                                normalize_text(result.get("screening_reason")) or "No reason provided"
                            )
                            stats.success_count += 1
                            changes_since_save += 1
                            if post_success_delay > 0:
                                time.sleep(post_success_delay)
                            break
                        except Exception as exc:
                            last_error = str(exc)
                            if attempt < max_retries - 1 and retry_delay > 0:
                                time.sleep(retry_delay)
                    else:
                        frame.at[row_index, "Screening_Result"] = "api_error"
                        frame.at[row_index, "Screening_Reason"] = last_error or "Unknown API error"
                        stats.api_error_count += 1
                        changes_since_save += 1

        if changes_since_save >= save_interval:
            save_screening_csv(frame, csv_path)
            changes_since_save = 0

    if changes_since_save > 0:
        save_screening_csv(frame, csv_path)

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screen full-text PDFs with an LLM and write results back to the sampled CSV."
    )
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_INPUT_FILE)
    parser.add_argument("--pdf-folder", type=Path, default=DEFAULT_PDF_FOLDER)
    parser.add_argument("--year-start", type=int, default=DEFAULT_YEAR_START)
    parser.add_argument("--year-end", type=int, default=DEFAULT_YEAR_END)
    parser.add_argument("--save-interval", type=int, default=DEFAULT_SAVE_INTERVAL)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY)
    parser.add_argument("--post-success-delay", type=float, default=DEFAULT_POST_SUCCESS_DELAY)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Loading dataset...")
    stats = process_screening_csv(
        csv_path=args.csv_path,
        pdf_folder=args.pdf_folder,
        year_start=args.year_start,
        year_end=args.year_end,
        save_interval=args.save_interval,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        post_success_delay=args.post_success_delay,
        model_name=args.model_name,
    )
    print(f"Total rows: {stats.total_rows}")
    print(f"Skipped existing rows: {stats.skipped_existing_count}")
    print(f"Excluded by year: {stats.excluded_by_year_count}")
    print(f"PDF missing: {stats.pdf_missing_count}")
    print(f"PDF read errors: {stats.pdf_read_error_count}")
    print(f"LLM screened successfully: {stats.success_count}")
    print(f"API errors: {stats.api_error_count}")
    print(f"Updated CSV: {args.csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())