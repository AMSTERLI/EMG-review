
# EMG Demographics Review — Project Overview

This repository contains scripts and datasets for a systematic review of participant demographics reported in Electromyography (EMG) studies. The workflow covers collecting records from PubMed and IEEE Xplore, merging exports, sampling papers for full-text review, extracting demographic details with an LLM, and saving structured results for manual verification.

## Workflow

```mermaid
graph TD
    %% 自定义节点颜色
    classDef script fill:#f9f2f4,stroke:#c7254e,stroke-width:2px,color:#c7254e;
    classDef data fill:#dff0d8,stroke:#3c763d,stroke-width:2px,color:#3c763d;
    classDef manual fill:#fcf8e3,stroke:#8a6d3b,stroke-width:2px,color:#8a6d3b;
    classDef analysis fill:#d9edf7,stroke:#31708f,stroke-width:2px,color:#31708f;

    %% 阶段 1: 数据收集与清理
    subgraph Phase 1: 数据检索与合并 (Data Retrieval & Merging)
        A1[PubMed 导出 CSV]:::data --> B(merge_csv.py):::script
        A2[IEEE 分批导出 CSV]:::data --> B
        B -->|列名对齐 / 标题去重 / 剔除无摘要项| C[(Final_Merged_Dataset.csv<br/>Total: 6242)]:::data
    end

    %% 阶段 2: 抽样与全文准备
    subgraph Phase 2: 随机抽样与全文本获取 (Sampling & PDF Fetching)
        C --> D(random_sample.py):::script
        D -->|random_state=42| E[(Sampled_200_Papers.csv)]:::data
        E -.->|依据 DOI/Title| F[人工/插件辅助下载 PDF]:::manual
        F --> G[PDF_Dataset 文件夹<br/>格式: ID.pdf]:::data
    end

    %% 阶段 3: 大语言模型自动化信息提取
    subgraph Phase 3: 自动化全文信息提取 (LLM Automated Extraction)
        E --> H(pdf_extractor.py):::script
        G -->|PyMuPDF 文本解析| H
        H -->|调用 Gemini/GPT API<br/>严格 JSON 格式输出| I[(Extracted_Demographics_Results.csv)]:::data
    end

    %% 阶段 4: 结果分析
    subgraph Phase 4: 结果分析与毕设撰写 (Analysis & Thesis)
        I --> J[数据可视化分析<br/>样本量/肤色/种族分布]:::analysis
        J --> K[撰写毕业论文:<br/>EMG研究中的人口统计学代表性偏差]:::analysis
    end

    %% 样式说明
    class A1,A2,C,E,G,I data;
    class B,D,H script;
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


