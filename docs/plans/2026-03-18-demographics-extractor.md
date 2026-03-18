# Demographics Extractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `demographics_extractor.py` to extract participant demographic details from full-text PDFs and write the results back into the sampled CSV.

**Architecture:** Reuse the same high-level structure as `pdf_extractor.py`: read the sampled CSV, locate each PDF by `ID`, extract text with PyMuPDF, call an OpenAI-compatible API with strict JSON output, and update the source CSV incrementally so runs can resume safely. Add dedicated demographics columns plus a status/error pair so incomplete and failed rows are explicit.

**Tech Stack:** Python, pandas, PyMuPDF, tqdm, openai-compatible client, unittest

---

### Task 1: Write demographics processing tests

**Files:**
- Create: `test_demographics_extractor.py`
- Modify: `demographics_extractor.py`

**Step 1: Write the failing test**

Add tests for:
- missing PDF marks `Demographics_Extraction_Status=pdf_missing`
- PDF read error marks `pdf_read_error`
- successful LLM extraction writes all demographics fields
- existing status skips the row
- repeated API failure marks `api_error`

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_demographics_extractor.py -v`
Expected: FAIL because `demographics_extractor.py` is not implemented yet.

**Step 3: Write minimal implementation**

Implement:
- shared API config style matching `pdf_extractor.py`
- prompt creation
- PDF text extraction
- CSV column initialization
- retry/save/resume logic

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_demographics_extractor.py -v`
Expected: PASS

### Task 2: Verify implementation quality

**Files:**
- Modify: `demographics_extractor.py`

**Step 1: Run focused validation**

Run:
- `python -m unittest test_demographics_extractor.py -v`
- inspect lints for `demographics_extractor.py`

**Step 2: Fix any issues**

Address failing tests or lint problems with minimal code changes.

**Step 3: Re-run validation**

Confirm tests pass and edited files are lint-clean.
