import pandas as pd
import numpy as np

# 1. 读取合并后的数据集
df = pd.read_csv('Final_Merged_Dataset.csv')

# 2. 设定目标样本总量
total_sample_size = 900

# 3. 按 'Year' 进行分层按比例抽样 (采用索引提取法，完美保留所有列)
sampled_indices = []

for year, group in df.groupby('Year'):
    # 计算当前层应该分配到的样本数 (四舍五入)
    sample_n = int(round((len(group) / len(df)) * total_sample_size))
    # 防止因四舍五入导致某一层样本量为0
    sample_n = max(1, sample_n) if len(group) > 0 else 0
    # 防止抽样数大于该层实际总量
    sample_n = min(sample_n, len(group))
    
    # 抽取对应数量的索引，并存入列表
    if sample_n > 0:
        sampled_indices.extend(group.sample(n=sample_n, random_state=42).index)

# 直接根据抽中的索引从原数据中提取，这样绝对不会丢失 'Year' 列
sampled_df = df.loc[sampled_indices].copy()

# (可选) 如果因四舍五入导致总数不是绝对的900篇，进行微调
current_n = len(sampled_df)
if current_n > total_sample_size:
    sampled_df = sampled_df.sample(n=total_sample_size, random_state=42)
elif current_n < total_sample_size:
    # 从未被抽中的数据中补齐差额
    remaining_df = df.drop(sampled_df.index)
    shortfall = total_sample_size - current_n
    sampled_df = pd.concat([sampled_df, remaining_df.sample(n=shortfall, random_state=42)])

# 4. 保存科学采样的结果
sampled_df.to_csv('Sampled_900_Papers_Stratified.csv', index=False)