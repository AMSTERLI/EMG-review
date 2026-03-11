#Author:Bingle    Date: 2025-03-10
#Convert a text file downloaded from PubMed to CSV
#===========================================

from Bio import Medline
import pandas as pd

# 1. Read the PubMed exported TXT file
with open("pubmed-Electromyo-set.txt", "r", encoding="utf-8") as f:
    records = Medline.parse(f)
    
    data = []
    for record in records:
        data.append({
            "PMID": record.get("PMID", ""),
            "Title": record.get("TI", ""),
            "Abstract": record.get("AB", ""), # this is the abstract we need
            "Year": record.get("DP", "")[:4]   # publication year
        })

# 2. Convert to DataFrame and save as CSV
df = pd.DataFrame(data)

# Filter out records without abstracts (some items may not have abstracts)
df_clean = df[df['Abstract'] != ""]

df_clean.to_csv("pubmed_with_abstracts.csv", index=False, encoding="utf-8")
print(f"Conversion successful! Extracted {len(df_clean)} records with abstracts.")