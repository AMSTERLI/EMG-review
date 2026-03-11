#Author:Bingle    Date: 2026-03-11
#Parse structured PubMed format into CSV using Bio.Medline
#===========================================

from Bio import Medline
import pandas as pd
import re

# ⚠️ 注意：请确保这个输入文件是你选择 Format: "PubMed" 导出的文件，而不是 "Abstract (text)"
input_txt = "./original-csv/pubmed-Electromyo-set.txt" 
output_csv = "./original-csv/pubmed_with_abstracts.csv"

data = []

# 1. 读取结构化的 PubMed 文件
print("正在解析 PubMed 结构化文件...")
with open(input_txt, "r", encoding="utf-8") as f:
    records = Medline.parse(f)
    
    for record in records:
        # PubMed 的出版日期字段 (DP) 格式通常是 "2000 Oct" 或 "2023 Jan-Feb"
        # 我们用正则从中精准提取出 4 位数的年份
        dp = record.get("DP", "")
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', dp)
        year = year_match.group(1) if year_match else ""

        data.append({
            "PMID": record.get("PMID", ""),
            "Title": record.get("TI", ""),
            "Abstract": record.get("AB", ""), # 精准提取 AB 标签下的摘要
            "Year": year
        })

# 2. 转换为 DataFrame 并清理数据
df = pd.DataFrame(data)

# 过滤掉没有摘要的文献
df_clean = df[df['Abstract'] != ""]
# 过滤掉没有年份的文献（可选，保证数据干净）
df_clean = df_clean[df_clean['Year'] != ""]

# 3. 保存为完美的 CSV
df_clean.to_csv(output_csv, index=False, encoding="utf-8-sig")
print(f"转换成功！共提取了 {len(df_clean)} 篇带有完整年份和摘要的文献。")