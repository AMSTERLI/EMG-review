# 为 Sampled_Papers_Stratified 统计论文来源设计

**目标：** 为 `PDF_Dataset/Sampled_Papers_Stratified.csv` 编写一个本地统计脚本，汇总论文来源中的 `Database`、`Journal` 和 `Country_of_Study` 分布，并输出归一化后的频数结果。

## 背景

当前采样表已经包含：

- `Database`
- `Journal`
- `Country_of_Study`

因此本次需求不需要调用外部 API，也不需要回写原始数据，只需要读取 CSV、对来源字段做基础清洗，然后生成可复用的统计结果。

## 方案比较

### 方案 1：直接按原始值统计

实现最简单，但会把 `USA`、`U.S.A.`、`United States` 之类的别名拆成多个类别，也会受到多余空格和大小写差异影响。

### 方案 2：基础归一化后统计

在统计前统一首尾空格、连续空格和常见国家别名，再输出频数表。这个方案复杂度低，结果更适合后续分析，推荐使用。

### 方案 3：高度规则化清洗

为数据库、期刊和国家建立更完整的映射字典，可以得到更整洁的统计结果，但当前需求没有足够样本规则支撑，容易过度设计。

## 推荐方案

采用方案 2：

1. 读取 `PDF_Dataset/Sampled_Papers_Stratified.csv`
2. 校验 `Database`、`Journal`、`Country_of_Study` 列存在
3. 对三列执行基础归一化
4. 对国家列额外合并常见英文别名
5. 分别统计三列的频数
6. 在终端打印摘要
7. 将结果保存为独立的统计 CSV 文件

## 数据规则

- 输入文件默认路径：`PDF_Dataset/Sampled_Papers_Stratified.csv`
- 输出目录默认路径：`analysis_outputs/source_stats`
- 空值、空白字符串和缺失值统一为 `Not reported`
- `Database`、`Journal`：
  - 去除首尾空格
  - 将连续空白压缩为单个空格
- `Country_of_Study`：
  - 先执行上述标准化
  - 再合并常见别名，例如：
    - `USA` / `U.S.A.` / `United States of America` -> `United States`
    - `UK` / `U.K.` -> `United Kingdom`

## 错误处理

- 输入文件不存在：抛出明确错误并退出
- 缺少必需列：抛出明确错误并指出列名
- 输出目录不存在：自动创建
- 某列全部为空：仍然输出统计文件，其中可能只包含 `Not reported`

## 输出设计

- 终端打印：
  - 输入文件路径
  - 总论文数
  - 每个字段的唯一值数量
  - 每个字段的前几项频数
- 文件输出：
  - `analysis_outputs/source_stats/database_counts.csv`
  - `analysis_outputs/source_stats/journal_counts.csv`
  - `analysis_outputs/source_stats/country_counts.csv`

每个输出文件包含：

- `value`
- `count`
- `percentage`

## 测试策略

- 为归一化函数编写单元测试
- 为统计函数编写单元测试，验证计数与百分比
- 为命令级流程编写测试，验证输出文件会被创建且内容正确

## 成功标准

- 能从默认采样表直接生成三份来源统计文件
- 国家别名会被合并到统一结果
- 空值会稳定归并到 `Not reported`
- 测试通过，脚本可重复运行
