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
DEFAULT_SAVE_INTERVAL = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 5.0
DEFAULT_POST_SUCCESS_DELAY = 2.0

DEMOGRAPHICS_COLUMNS = (
    "Sample_Size",
    "Gender_Details",
    "Age_Details",
    "Race_Ethnicity_Details",
    "Country_of_Study",
    "Extraction_Notes",
    "Demographics_Extraction_Status",
    "Demographics_Extraction_Error",
)


@dataclass
class DemographicsStats:
    total_rows: int
    skipped_existing_count: int = 0
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


def normalize_reported_text(value: object) -> str:
    text = normalize_text(value)
    return text if text else "Not reported"


def normalize_sample_size(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None

    text = normalize_text(value)
    if not text or text.lower() == "null":
        return None

    try:
        numeric_value = float(text)
    except ValueError:
        return None

    return int(numeric_value) if numeric_value.is_integer() else None


def ensure_demographics_columns(frame: pd.DataFrame) -> pd.DataFrame:
    working_frame = frame.copy()
    for column in DEMOGRAPHICS_COLUMNS:
        if column not in working_frame.columns:
            working_frame[column] = ""
    return working_frame


def save_demographics_csv(frame: pd.DataFrame, csv_path: Path) -> None:
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


def create_demographics_prompt(title: str, full_text: str) -> str:
    return f"""You are an expert academic data extractor assisting with a systematic review on demographic representation in Electromyography (EMG) studies.

Your task is to thoroughly read the following full-text research paper and extract specific demographic information about the human participants. Pay close attention to the "Methods", "Participants", "Subjects", or "Data Collection" sections.

Paper Title: {title}
---
Full Text:
{full_text}
---

Extract the required information and return it STRICTLY in JSON format with exactly the following keys. If a specific piece of information is NOT reported in the text, you MUST output "Not reported" (for strings) or null (for numbers). Do not guess or infer missing data.

{{
    "sample_size": "Total number of human participants (integer). If not explicitly stated, output null.",
    "gender_details": "Extract the exact gender breakdown if reported (e.g., '10 Males, 5 Females', '60% Male'). If not reported, output 'Not reported'.",
    "age_details": "Extract the age information, including mean, standard deviation (SD), and range if available (e.g., 'Mean 25.4 ± 3.2 years, range 18-35'). If not reported, output 'Not reported'.",
    "race_ethnicity_details": "Extract the exact racial, ethnic, or skin color/tone breakdown if reported (e.g., '10 Caucasian, 5 Asian', 'Fitzpatrick skin type II-IV'). If the paper explicitly states the participants' race/ethnicity, write it here. If completely unmentioned, output 'Not reported'.",
    "country_of_study": "Identify the country where the study was conducted or the data was collected. Look at the authors' affiliations or the study setting. If ambiguous, output 'Not reported'.",
    "extraction_notes": "A brief 1-2 sentence note explaining where you found the demographic data, or confirming if demographic reporting was severely lacking."
}}"""


def extract_demographics_with_llm(
    title: str,
    full_text: str,
    *,
    client=None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, object]:
    llm_client = client or build_client()
    prompt = create_demographics_prompt(title, full_text[:100000])
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
        "sample_size": normalize_sample_size(parsed.get("sample_size")),
        "gender_details": normalize_reported_text(parsed.get("gender_details")),
        "age_details": normalize_reported_text(parsed.get("age_details")),
        "race_ethnicity_details": normalize_reported_text(parsed.get("race_ethnicity_details")),
        "country_of_study": normalize_reported_text(parsed.get("country_of_study")),
        "extraction_notes": normalize_reported_text(parsed.get("extraction_notes")),
    }


def process_demographics_csv(
    *,
    csv_path: Path,
    pdf_folder: Path,
    save_interval: int = DEFAULT_SAVE_INTERVAL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    post_success_delay: float = DEFAULT_POST_SUCCESS_DELAY,
    client=None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> DemographicsStats:
    csv_path = Path(csv_path)
    pdf_folder = Path(pdf_folder)

    frame = ensure_demographics_columns(pd.read_csv(csv_path, encoding="utf-8-sig"))
    stats = DemographicsStats(total_rows=len(frame))
    changes_since_save = 0

    for row_index, row in tqdm(frame.iterrows(), total=len(frame), desc="Extracting demographics"):
        if normalize_text(row.get("Demographics_Extraction_Status")):
            stats.skipped_existing_count += 1
            continue

        doc_id = normalize_text(row.get("ID", row_index))
        safe_doc_id = doc_id.replace("/", "_")
        pdf_path = pdf_folder / f"{safe_doc_id}.pdf"

        if not pdf_path.exists():
            frame.at[row_index, "Demographics_Extraction_Status"] = "pdf_missing"
            frame.at[row_index, "Demographics_Extraction_Error"] = "PDF file not found"
            stats.pdf_missing_count += 1
            changes_since_save += 1
        else:
            full_text = extract_text_from_pdf(pdf_path)
            if full_text.startswith("Error"):
                frame.at[row_index, "Demographics_Extraction_Status"] = "pdf_read_error"
                frame.at[row_index, "Demographics_Extraction_Error"] = full_text
                stats.pdf_read_error_count += 1
                changes_since_save += 1
            else:
                title = normalize_text(row.get("Title"))
                last_error = ""
                for attempt in range(max_retries):
                    try:
                        result = extract_demographics_with_llm(
                            title,
                            full_text,
                            client=client,
                            model_name=model_name,
                        )
                        sample_size = normalize_sample_size(result.get("sample_size"))
                        frame.at[row_index, "Sample_Size"] = "" if sample_size is None else str(sample_size)
                        frame.at[row_index, "Gender_Details"] = normalize_reported_text(
                            result.get("gender_details")
                        )
                        frame.at[row_index, "Age_Details"] = normalize_reported_text(
                            result.get("age_details")
                        )
                        frame.at[row_index, "Race_Ethnicity_Details"] = normalize_reported_text(
                            result.get("race_ethnicity_details")
                        )
                        frame.at[row_index, "Country_of_Study"] = normalize_reported_text(
                            result.get("country_of_study")
                        )
                        frame.at[row_index, "Extraction_Notes"] = normalize_reported_text(
                            result.get("extraction_notes")
                        )
                        frame.at[row_index, "Demographics_Extraction_Status"] = "success"
                        frame.at[row_index, "Demographics_Extraction_Error"] = ""
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
                    frame.at[row_index, "Demographics_Extraction_Status"] = "api_error"
                    frame.at[row_index, "Demographics_Extraction_Error"] = (
                        last_error or "Unknown API error"
                    )
                    stats.api_error_count += 1
                    changes_since_save += 1

        if changes_since_save >= save_interval:
            save_demographics_csv(frame, csv_path)
            changes_since_save = 0

    if changes_since_save > 0:
        save_demographics_csv(frame, csv_path)

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract participant demographics from full-text PDFs and write them back to the sampled CSV."
    )
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_INPUT_FILE)
    parser.add_argument("--pdf-folder", type=Path, default=DEFAULT_PDF_FOLDER)
    parser.add_argument("--save-interval", type=int, default=DEFAULT_SAVE_INTERVAL)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--retry-delay", type=float, default=DEFAULT_RETRY_DELAY)
    parser.add_argument("--post-success-delay", type=float, default=DEFAULT_POST_SUCCESS_DELAY)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Loading dataset...")
    stats = process_demographics_csv(
        csv_path=args.csv_path,
        pdf_folder=args.pdf_folder,
        save_interval=args.save_interval,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        post_success_delay=args.post_success_delay,
        model_name=args.model_name,
    )
    print(f"Total rows: {stats.total_rows}")
    print(f"Skipped existing rows: {stats.skipped_existing_count}")
    print(f"PDF missing: {stats.pdf_missing_count}")
    print(f"PDF read errors: {stats.pdf_read_error_count}")
    print(f"LLM extracted successfully: {stats.success_count}")
    print(f"API errors: {stats.api_error_count}")
    print(f"Updated CSV: {args.csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
