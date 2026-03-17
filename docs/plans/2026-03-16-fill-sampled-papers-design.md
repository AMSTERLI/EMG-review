# 补齐 Sampled_Papers_Stratified 到 400 篇设计

**目标：** 统计 `PDF_Dataset/Sampled_Papers_Stratified.csv` 中各年份论文数，并在总量不足 `400` 篇时，从 `original-csv/merged_sampled_ieee_pubmed_2000_2026.csv` 中按年份比例随机补样，使补齐后的年度分布尽量与 `merged_sampled_ieee_pubmed_2000_2026.csv` 一致。

## 背景

当前仓库已经有：

- `merge_sampled_ieee_pubmed.py`：合并 IEEE 与 PubMed 采样结果
- `prune_pdf_dataset_to_merged_titles.py`：按标题过滤 PDF 数据集

这次需求不是“重新整体采样”，而是“在已有样本上补齐缺口并保持总体年份分布”，因此应使用独立脚本，避免混淆现有采样与清理流程。

## 方案比较

### 方案 1：按四舍五入计算每年目标数

实现简单，但会因为舍入误差导致总量不一定严格等于 `400`，后续还需要二次调整，结果不够稳定。

### 方案 2：按年份比例 + 最大余数法分配目标数

先依据 `merged` 的年份占比计算每年的浮点目标数，再用最大余数法把目标数精确分配到 `400` 篇。这一方案能够保证总量严格正确，且年度分布与源数据最接近。推荐使用。

### 方案 3：直接从 merged 再做一次整体分层抽样

不推荐。这样会破坏 `Sampled_Papers_Stratified.csv` 现有已选样本，不符合“补缺”而不是“重采样”的要求。

## 推荐方案

采用方案 2：新增独立脚本，读取当前样本和来源全集，先保留现有样本，再按年份缺口补样。

## 数据规则

- 判重键：按 `Title` 去重
- 补入记录的 `Status`：默认填空值
- 随机采样：使用固定随机种子，保证结果可复现
- 若某年份可补数量小于缺口：直接报错，避免 silently 少抽

## 数据流

1. 读取 `PDF_Dataset/Sampled_Papers_Stratified.csv`
2. 读取 `original-csv/merged_sampled_ieee_pubmed_2000_2026.csv`
3. 统计 `merged` 中各年份数量
4. 按 `target_total=400` 计算每年的目标数
5. 统计当前样本中各年份已有数量
6. 对每个年份计算缺口 `target_count - current_count`
7. 从 `merged` 中筛出该年份、且标题未在当前样本中出现的候选论文
8. 对候选论文做随机抽样并补入当前样本
9. 输出补齐后的 CSV
10. 输出年度统计表，并在终端打印摘要

## 输出设计

脚本默认输出两份文件：

- `PDF_Dataset/Sampled_Papers_Stratified_filled.csv`
- `PDF_Dataset/Sampled_Papers_Stratified_year_stats.csv`

统计表至少包含这些列：

- `Year`
- `MergedCount`
- `MergedRatio`
- `CurrentCount`
- `TargetCount`
- `AddedCount`
- `FinalCount`

## 错误处理

- 输入文件缺失：抛出清晰错误
- 缺少必需列：抛出清晰错误
- 当前样本已超过目标总数：抛出错误
- 某年份无法补足：抛出错误并标出年份、缺口和可用候选数

## 测试策略

至少覆盖以下行为：

- 目标篇数严格等于 `400`
- 年份目标数使用最大余数法正确分配
- 已有样本按 `Title` 排除，不会重复补入
- 新补入记录的 `Status` 为空值
- 会生成补齐结果文件与年份统计文件

## 成功标准

- 脚本可直接运行并补齐到目标总数
- 补齐后的年份分布与 `merged` 的年份分布一致或最接近
- 不会引入与当前样本同标题的重复记录
- 能输出人可读的年度统计结果
