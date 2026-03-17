# Fill Sampled Papers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone Python script that fills `PDF_Dataset/Sampled_Papers_Stratified.csv` up to 400 total rows by randomly sampling missing papers from `original-csv/merged_sampled_ieee_pubmed_2000_2026.csv`, while preserving the merged dataset's year distribution and avoiding duplicate titles.

**Architecture:** Add one standalone script and one unittest file. The script will load both CSV files, compute year targets from the merged dataset using the largest remainder method, measure current counts, sample shortfalls by year from rows not already present by title, append the sampled rows with empty `Status`, write the filled CSV, and write a year statistics CSV.

**Tech Stack:** Python 3, pandas, unittest, subprocess, tempfile

---

### Task 1: Create failing tests for year target allocation and fill behavior

**Files:**
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/fill_sampled_papers_to_target.py`
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_sampled_papers_to_target.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_sampled_papers_to_target.py`

**Step 1: Write the failing test**

```python
def test_fills_missing_rows_to_target_without_duplicate_titles():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_fill_sampled_papers_to_target.py -v`
Expected: FAIL because the target script does not exist or required behavior is missing.

**Step 3: Write minimal implementation**

```python
candidate_frame = source_year_frame[~source_year_frame["Title"].isin(existing_titles)]
sampled = candidate_frame.sample(n=shortfall, random_state=random_seed)
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_fill_sampled_papers_to_target.py -v`
Expected: PASS for the new fill behavior.

**Step 5: Commit**

```bash
git add test_fill_sampled_papers_to_target.py fill_sampled_papers_to_target.py
git commit -m "feat: fill sampled papers to target size"
```

### Task 2: Add yearly stats output and CLI reporting

**Files:**
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/fill_sampled_papers_to_target.py`
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_sampled_papers_to_target.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_sampled_papers_to_target.py`

**Step 1: Write the failing test**

```python
def test_writes_year_stats_and_reports_summary():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_fill_sampled_papers_to_target.py -v`
Expected: FAIL because the script does not yet write the statistics file or print the expected summary.

**Step 3: Write minimal implementation**

```python
stats_frame.to_csv(stats_path, index=False, encoding="utf-8-sig")
print(f"Filled rows: {len(added_frame)}")
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_fill_sampled_papers_to_target.py -v`
Expected: PASS with generated output files and matching yearly statistics.

**Step 5: Commit**

```bash
git add test_fill_sampled_papers_to_target.py fill_sampled_papers_to_target.py
git commit -m "feat: report sampled paper fill statistics"
```
