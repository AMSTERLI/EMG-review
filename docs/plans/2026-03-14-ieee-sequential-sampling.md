# IEEE Sequential Sampling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone Python script that samples 30% of each IEEE yearly CSV in file order from `2000.csv` through `2026.csv`, rounds sample counts up, merges the sampled rows into one CSV, and reports per-year counts.

**Architecture:** Add one standalone script at the repository root and one standalone unittest file. The script will iterate years in ascending order, read yearly CSVs from `original-csv`, compute `ceil(n * 0.3)`, take `iloc[:sample_count]`, concatenate results, write one merged CSV, and print a year-by-year summary plus totals.

**Tech Stack:** Python 3, pandas, unittest, subprocess, tempfile

---

### Task 1: Create failing tests for sampling math and ordering

**Files:**
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/test_sequential_sample_ieee_years.py`
- Create: `C:/Users/LBL99/Desktop/Project/EMG-review/sequential_sample_ieee_years.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_sequential_sample_ieee_years.py`

**Step 1: Write the failing test**

```python
def test_samples_30_percent_per_year_with_ceiling_and_keeps_order():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_sequential_sample_ieee_years.py -v`
Expected: FAIL because the target script does not exist or required behavior is missing.

**Step 3: Write minimal implementation**

```python
sample_count = math.ceil(len(frame) * 0.3)
sampled = frame.iloc[:sample_count].copy()
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_sequential_sample_ieee_years.py -v`
Expected: PASS for the new behavior.

**Step 5: Commit**

```bash
git add test_sequential_sample_ieee_years.py sequential_sample_ieee_years.py
git commit -m "feat: add sequential IEEE yearly sampler"
```

### Task 2: Add merged output and summary reporting

**Files:**
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/sequential_sample_ieee_years.py`
- Modify: `C:/Users/LBL99/Desktop/Project/EMG-review/test_sequential_sample_ieee_years.py`
- Test: `C:/Users/LBL99/Desktop/Project/EMG-review/test_sequential_sample_ieee_years.py`

**Step 1: Write the failing test**

```python
def test_writes_merged_output_and_reports_yearly_counts():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_sequential_sample_ieee_years.py -v`
Expected: FAIL because the script does not yet print the expected yearly summary or create the merged output file correctly.

**Step 3: Write minimal implementation**

```python
combined.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"{year}: total={total_rows}, sampled={sample_count}")
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_sequential_sample_ieee_years.py -v`
Expected: PASS with generated output file and matching yearly counts.

**Step 5: Commit**

```bash
git add test_sequential_sample_ieee_years.py sequential_sample_ieee_years.py
git commit -m "feat: report yearly IEEE sequential sampling counts"
```
