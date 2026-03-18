import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import demographics_extractor


class DemographicsExtractorTests(unittest.TestCase):
    def test_marks_pdf_missing_without_calling_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "2",
                        "Title": "Needs pdf",
                        "Year": "2020",
                    }
                ],
            )

            with patch.object(demographics_extractor, "extract_demographics_with_llm") as mocked_llm:
                stats = demographics_extractor.process_demographics_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Demographics_Extraction_Status"], "pdf_missing")
            self.assertEqual(rows[0]["Demographics_Extraction_Error"], "PDF file not found")
            self.assertEqual(stats.pdf_missing_count, 1)
            mocked_llm.assert_not_called()

    def test_marks_pdf_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()
            (pdf_dir / "3.pdf").write_bytes(b"%PDF-1.4 fake")

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "3",
                        "Title": "Unreadable pdf",
                        "Year": "2021",
                    }
                ],
            )

            with patch.object(
                demographics_extractor,
                "extract_text_from_pdf",
                return_value="Error reading PDF: broken file",
            ), patch.object(demographics_extractor, "extract_demographics_with_llm") as mocked_llm:
                stats = demographics_extractor.process_demographics_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Demographics_Extraction_Status"], "pdf_read_error")
            self.assertEqual(rows[0]["Demographics_Extraction_Error"], "Error reading PDF: broken file")
            self.assertEqual(stats.pdf_read_error_count, 1)
            mocked_llm.assert_not_called()

    def test_writes_extracted_demographics_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()
            (pdf_dir / "4.pdf").write_bytes(b"%PDF-1.4 fake")

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "4",
                        "Title": "Eligible paper",
                        "Year": "2021",
                    }
                ],
            )

            with patch.object(
                demographics_extractor,
                "extract_text_from_pdf",
                return_value="Methods with 15 participants, 10 males and 5 females.",
            ), patch.object(
                demographics_extractor,
                "extract_demographics_with_llm",
                return_value={
                    "sample_size": 15,
                    "gender_details": "10 Males, 5 Females",
                    "age_details": "Mean 25.4 +- 3.2 years",
                    "race_ethnicity_details": "Not reported",
                    "country_of_study": "Canada",
                    "extraction_notes": "Found in the participants subsection.",
                },
            ) as mocked_llm:
                stats = demographics_extractor.process_demographics_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Sample_Size"], "15")
            self.assertEqual(rows[0]["Gender_Details"], "10 Males, 5 Females")
            self.assertEqual(rows[0]["Age_Details"], "Mean 25.4 +- 3.2 years")
            self.assertEqual(rows[0]["Race_Ethnicity_Details"], "Not reported")
            self.assertEqual(rows[0]["Country_of_Study"], "Canada")
            self.assertEqual(rows[0]["Extraction_Notes"], "Found in the participants subsection.")
            self.assertEqual(rows[0]["Demographics_Extraction_Status"], "success")
            self.assertEqual(rows[0]["Demographics_Extraction_Error"], "")
            self.assertEqual(stats.success_count, 1)
            mocked_llm.assert_called_once()

    def test_skips_rows_with_existing_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "5",
                        "Title": "Already extracted",
                        "Year": "2022",
                        "Demographics_Extraction_Status": "success",
                        "Sample_Size": "20",
                    }
                ],
            )

            with patch.object(demographics_extractor, "extract_demographics_with_llm") as mocked_llm:
                stats = demographics_extractor.process_demographics_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Demographics_Extraction_Status"], "success")
            self.assertEqual(rows[0]["Sample_Size"], "20")
            self.assertEqual(stats.skipped_existing_count, 1)
            mocked_llm.assert_not_called()

    def test_marks_api_error_after_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()
            (pdf_dir / "6.pdf").write_bytes(b"%PDF-1.4 fake")

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "6",
                        "Title": "API failure paper",
                        "Year": "2022",
                    }
                ],
            )

            with patch.object(
                demographics_extractor,
                "extract_text_from_pdf",
                return_value="Participants data",
            ), patch.object(
                demographics_extractor,
                "extract_demographics_with_llm",
                side_effect=RuntimeError("temporary API failure"),
            ):
                stats = demographics_extractor.process_demographics_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    save_interval=1,
                    max_retries=2,
                    retry_delay=0,
                    post_success_delay=0,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Demographics_Extraction_Status"], "api_error")
            self.assertEqual(rows[0]["Demographics_Extraction_Error"], "temporary API failure")
            self.assertEqual(stats.api_error_count, 1)

    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
