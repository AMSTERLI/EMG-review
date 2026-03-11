
# EMG Demographics Review — Project Overview

This repository contains scripts and datasets for a systematic review of participant demographics reported in Electromyography (EMG) studies. The workflow covers collecting records from PubMed and IEEE Xplore, merging exports, sampling papers for full-text review, extracting demographic details with an LLM, and saving structured results for manual verification.

## Workflow

```mermaid
graph TD
    subgraph phase1 ["Phase 1: Data Retrieval & Merging"]
        A1[PubMed CSV] --> B(merge_csv.py)
        A2[IEEE CSV] --> B
        B -->|Merge & Deduplicate| C[(Final_Merged_Dataset.csv)]
    end

    subgraph phase2 ["Phase 2: Sampling & PDF Fetching"]
        C --> D(random_sample.py)
        D -->|random_state=42| E[(Sampled_200_Papers.csv)]
        E -.->|Manual/Plugin| F[Download PDFs]
        F --> G[PDF_Dataset Folder]
    end

    subgraph phase3 ["Phase 3: LLM Automated Extraction"]
        E --> H(pdf_extractor.py)
        G -->|PyMuPDF Text| H
        H -->|LLM API Call| I[(Extracted_Demographics.csv)]
    end

    subgraph phase4 ["Phase 4: Analysis & Thesis"]
        I --> J[Data Visualization]
        J --> K[Thesis Writing]
    end
```

## Dataset
- Original exports from PubMed and IEEE Xplore are placed under the project root (e.g., `export*.csv`, `pubmed-Electromyo-set.txt`).
- `Final_Merged_Dataset.csv`: cleaned merge of PubMed and IEEE records (titles + abstracts).
- `Sampled_10_Papers.csv`: example random sample of 10 papers (you will sample 600 in the full study).
- `PDF_Dataset/`: directory to store downloaded PDFs (named by article ID with `/` replaced by `_`).

## Key Scripts
- `get_csv.py` — Parse the PubMed text export (`pubmed-Electromyo-set.txt`) and produce `pubmed_with_abstracts.csv`.
- `merge_csv.py` — Merge PubMed and IEEE CSV exports into `Final_Merged_Dataset.csv`. Removes entries without abstracts and deduplicates by title.
- `random_sample.py` — Randomly sample N articles from `Final_Merged_Dataset.csv`. Default example samples 10; change `n=` to 600 for your main run.
- `pdf_extractor.py` — Read PDFs from `PDF_Dataset`, send full text to an LLM, and extract structured demographic fields into `Extracted_Demographics_Results.csv` (resumable and incremental saving).

## Requirements
- Python 3.8+
- Install dependencies:

```bash
pip install pandas biopython tqdm pymupdf openai
```

Adjust versions as needed. `pymupdf` provides `fitz` for PDF parsing; `biopython` provides `Bio.Medline`.

## Configuration
- Each script contains a small configuration block near the top (model name, `input_file`, `output_file`, and `pdf_folder`).
- Update the OpenAI/proxy `api_key` and `base_url` in the scripts before running (or modify scripts to read from environment variables).

## Typical Workflow
1. Convert PubMed text export to CSV:

```bash
python get_csv.py
```

2. Merge PubMed and IEEE exports:

```bash
python merge_csv.py
```

3. Create a random sample (set `n=600` in `random_sample.py` for the main run):

```bash
python random_sample.py
```

4. Manually download full-text PDFs for sampled records into `PDF_Dataset/`. Name each file using the serial number.

5. Run full-text extraction (this will call the LLM and save incremental results):

```bash
python pdf_extractor.py
```


## Outputs
- `Final_Merged_Dataset.csv`: merged and cleaned title/abstract dataset.
- `Sampled_10_Papers.csv` / `Sampled_600_Papers.csv`: sampled lists.
- `Extracted_Demographics_Results.csv`: structured LLM-extracted demographic fields from full texts.

## Notes & Best Practices
- LLM outputs can hallucinate; always perform manual checks of extracted demographic entries before analysis.
- Scripts implement resumable behavior: if an output file already exists, processed IDs are skipped so interrupted runs can resume.
- `pdf_extractor.py` truncates full text to the first 100,000 characters to keep payloads reasonable — this usually includes Methods/Participants sections but verify if more context is needed.
- Adjust `save_interval` and retry settings in scripts to balance speed and reliability.

## Next Steps
- Replace hardcoded API keys with environment variables for security.
- Expand sampling from 10 to 600 and run the full pipeline.
- Add basic unit tests or a `requirements.txt` / `pyproject.toml` for reproducibility.


