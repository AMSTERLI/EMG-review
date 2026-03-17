# Fill Journal Column Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python script that adds or updates a `Journal` column in `PDF_Dataset/Sampled_Papers_Stratified.csv` by querying online metadata services using each paper title.

**Architecture:** Add one standalone script and one unittest file. The script will load the CSV, add `Journal` if missing, skip rows that already have a non-empty journal value, resolve journal names through `Crossref` first and `PubMed` as fallback for PubMed rows, then write the updated CSV back in place.

**Tech Stack:** Python 3, csv/pandas, urllib, json, unittest, unittest.mock

---

### Task 1: Create failing tests for column creation and row updates

**Files:**
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/fill_journal_column.py`
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_journal_column.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_journal_column.py`

**Step 1: Write the failing test**

```python
def test_adds_journal_column_and_fills_missing_values():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_fill_journal_column.py -v`
Expected: FAIL because the script does not exist or behavior is missing.

**Step 3: Write minimal implementation**

```python
if "Journal" not in frame.columns:
    frame["Journal"] = ""
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_fill_journal_column.py -v`
Expected: PASS for journal column creation and update behavior.

**Step 5: Commit**

```bash
git add test_fill_journal_column.py fill_journal_column.py
git commit -m "feat: fill journal metadata column"
```

### Task 2: Add fallback resolution and resumable behavior

**Files:**
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/fill_journal_column.py`
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_journal_column.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_fill_journal_column.py`

**Step 1: Write the failing test**

```python
def test_skips_existing_journal_values_and_uses_pubmed_fallback():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_fill_journal_column.py -v`
Expected: FAIL because the script does not yet skip filled rows or use fallback resolution.

**Step 3: Write minimal implementation**

```python
if journal_value:
    continue
journal = resolve_crossref(title) or resolve_pubmed(title)
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_fill_journal_column.py -v`
Expected: PASS with resumable updates and fallback behavior.

**Step 5: Commit**

```bash
git add test_fill_journal_column.py fill_journal_column.py
git commit -m "feat: add fallback journal resolution"
```
