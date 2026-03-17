import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pdf_extractor


class PdfExtractorScreeningTests(unittest.TestCase):
    def test_excludes_out_of_range_year_without_calling_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "1",
                        "Title": "Old paper",
                        "Abstract": "A",
                        "Year": "2014",
                        "Database": "PubMed",
                        "Journal": "",
                    }
                ],
            )

            with patch.object(pdf_extractor, "screen_pdf_with_llm") as mocked_llm:
                stats = pdf_extractor.process_screening_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    year_start=2016,
                    year_end=2026,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Screening_Result"], "exclude")
            self.assertEqual(rows[0]["Screening_Reason"], "Published outside 2016-2026")
            self.assertEqual(stats.excluded_by_year_count, 1)
            mocked_llm.assert_not_called()

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
                        "Abstract": "B",
                        "Year": "2020",
                        "Database": "IEEE",
                        "Journal": "",
                    }
                ],
            )

            with patch.object(pdf_extractor, "screen_pdf_with_llm") as mocked_llm:
                stats = pdf_extractor.process_screening_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    year_start=2016,
                    year_end=2026,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Screening_Result"], "pdf_missing")
            self.assertEqual(rows[0]["Screening_Reason"], "PDF file not found")
            self.assertEqual(stats.pdf_missing_count, 1)
            mocked_llm.assert_not_called()

    def test_skips_rows_with_existing_screening_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            csv_path = base_path / "sampled.csv"
            pdf_dir = base_path / "PDF_Dataset"
            pdf_dir.mkdir()

            self._write_csv(
                csv_path,
                rows=[
                    {
                        "ID": "3",
                        "Title": "Already screened",
                        "Abstract": "C",
                        "Year": "2020",
                        "Database": "PubMed",
                        "Journal": "",
                        "Screening_Result": "include",
                        "Screening_Reason": "Previously screened",
                    }
                ],
            )

            with patch.object(pdf_extractor, "screen_pdf_with_llm") as mocked_llm:
                stats = pdf_extractor.process_screening_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    year_start=2016,
                    year_end=2026,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Screening_Result"], "include")
            self.assertEqual(rows[0]["Screening_Reason"], "Previously screened")
            self.assertEqual(stats.skipped_existing_count, 1)
            mocked_llm.assert_not_called()

    def test_writes_llm_screening_result_and_reason(self) -> None:
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
                        "Abstract": "D",
                        "Year": "2021",
                        "Database": "PubMed",
                        "Journal": "",
                    }
                ],
            )

            with patch.object(pdf_extractor, "extract_text_from_pdf", return_value="Methods with human participants and sEMG"), patch.object(
                pdf_extractor,
                "screen_pdf_with_llm",
                return_value={
                    "screening_result": "include",
                    "screening_reason": "Primary human EMG study within timeframe.",
                },
            ) as mocked_llm:
                stats = pdf_extractor.process_screening_csv(
                    csv_path=csv_path,
                    pdf_folder=pdf_dir,
                    year_start=2016,
                    year_end=2026,
                    save_interval=1,
                )

            rows = self._read_rows(csv_path)
            self.assertEqual(rows[0]["Screening_Result"], "include")
            self.assertEqual(
                rows[0]["Screening_Reason"],
                "Primary human EMG study within timeframe.",
            )
            self.assertEqual(stats.success_count, 1)
            mocked_llm.assert_called_once()

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
