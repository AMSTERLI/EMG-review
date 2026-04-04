# Source Stats Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `PDF_Dataset/Sampled_Papers_Stratified.csv` 生成数据库、期刊和国家三个来源字段的归一化统计结果，并保存为独立 CSV 文件。

**Architecture:** 新增一个独立的 Python 脚本负责读取采样表、归一化字段值、聚合频数并输出结果。测试放在独立测试文件中，先验证归一化和统计逻辑，再验证文件输出，避免与现有 LLM 抽取流程耦合。

**Tech Stack:** Python 3, pandas, pathlib, unittest

---

### Task 1: 建立失败测试

**Files:**
- Create: `test_source_stats.py`
- Test: `test_source_stats.py`

**Step 1: Write the failing test**

```python
def test_normalize_country_aliases():
    assert source_stats.normalize_country("U.S.A.") == "United States"
```

```python
def test_build_counts_groups_normalized_values():
    rows = [
        {"Country_of_Study": "USA"},
        {"Country_of_Study": "United States"},
        {"Country_of_Study": ""},
    ]
    counts = source_stats.build_counts_frame(rows, "Country_of_Study")
    assert list(counts["value"]) == ["United States", "Not reported"]
    assert list(counts["count"]) == [2, 1]
```

```python
def test_write_outputs_creates_expected_csv_files():
    summary = source_stats.write_source_statistics(...)
    assert summary["total_rows"] == 3
    assert (output_dir / "country_counts.csv").exists()
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_source_stats.py`
Expected: FAIL because `source_stats.py` and tested functions do not exist yet.

**Step 3: Write minimal implementation**

```python
def normalize_country(value: object) -> str:
    ...
```

```python
def build_counts_frame(frame: pd.DataFrame, column_name: str) -> pd.DataFrame:
    ...
```

```python
def write_source_statistics(csv_path: Path, output_dir: Path) -> dict[str, object]:
    ...
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_source_stats.py`
Expected: PASS

**Step 5: Commit**

```bash
git add test_source_stats.py source_stats.py
git commit -m "add normalized source statistics script"
```

### Task 2: 实现命令行脚本

**Files:**
- Create: `source_stats.py`
- Modify: `readme.md`
- Test: `test_source_stats.py`

**Step 1: Write the failing test**

```python
def test_main_prints_top_counts_in_summary():
    exit_code = source_stats.main()
    assert exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest test_source_stats.py`
Expected: FAIL because CLI wiring is incomplete.

**Step 3: Write minimal implementation**

```python
def parse_args() -> argparse.Namespace:
    ...

def main() -> int:
    ...
```

Include:
- default input path `PDF_Dataset/Sampled_Papers_Stratified.csv`
- default output path `analysis_outputs/source_stats`
- terminal summary printing

**Step 4: Run test to verify it passes**

Run: `python -m unittest test_source_stats.py`
Expected: PASS

**Step 5: Commit**

```bash
git add test_source_stats.py source_stats.py readme.md
git commit -m "document source statistics workflow"
```

### Task 3: 验证与收尾

**Files:**
- Modify: `source_stats.py`
- Modify: `readme.md`
- Test: `test_source_stats.py`

**Step 1: Run focused tests**

Run: `python -m unittest test_source_stats.py`
Expected: PASS

**Step 2: Run related existing tests**

Run: `python -m unittest test_demographics_extractor.py`
Expected: PASS to confirm new script does not affect existing behavior.

**Step 3: Run script on the real CSV**

Run: `python source_stats.py`
Expected:
- prints summary for `Database`, `Journal`, `Country_of_Study`
- creates output files under `analysis_outputs/source_stats`

**Step 4: Review output**

Confirm:
- country aliases are merged
- missing values become `Not reported`
- percentages are present and human-readable

**Step 5: Commit**

```bash
git add source_stats.py test_source_stats.py readme.md analysis_outputs/source_stats/*.csv
git commit -m "add paper source statistics outputs"
```
