#Author:Bingle    Date: 2026-03-11
#Merge CSV files from the PubMed and IEEE Xplore databases.
#===========================================


import pandas as pd
import glob

print("Processing data, please wait...")

# ==========================================
# 1. Process PubMed data
# ==========================================
try:
    df_pubmed = pd.read_csv("./original-csv/pubmed_with_abstracts.csv", on_bad_lines='skip')
except FileNotFoundError:
    print("Warning: pubmed_with_abstracts.csv not found. Skipping PubMed.")
    df_pubmed = pd.DataFrame()

if not df_pubmed.empty:
    df_pubmed['Database'] = 'PubMed'
    if 'PMID' in df_pubmed.columns:
        df_pubmed.rename(columns={'PMID': 'ID'}, inplace=True)

cols_to_keep = ['ID', 'Title', 'Abstract', 'Year', 'Database']
for col in cols_to_keep:
    if col not in df_pubmed.columns:
        df_pubmed[col] = ""
df_pubmed = df_pubmed[cols_to_keep]

# ==========================================
# 2. Process IEEE data
# ==========================================
ieee_files = glob.glob("original-csv/export*.csv")
ieee_list = []

for file in ieee_files:
    try:
        # use on_bad_lines='skip' to ignore malformed rows
        temp_df = pd.read_csv(file, on_bad_lines='skip', encoding='utf-8')
    except Exception:
        temp_df = pd.read_csv(file, on_bad_lines='skip', encoding='latin1')
    ieee_list.append(temp_df)

if ieee_list:
    df_ieee_raw = pd.concat(ieee_list, ignore_index=True)
    df_ieee = pd.DataFrame()
    df_ieee['Title'] = df_ieee_raw['Document Title'] if 'Document Title' in df_ieee_raw.columns else ""
    df_ieee['Abstract'] = df_ieee_raw['Abstract'] if 'Abstract' in df_ieee_raw.columns else ""
    df_ieee['Year'] = df_ieee_raw['Publication Year'] if 'Publication Year' in df_ieee_raw.columns else ""
    df_ieee['ID'] = df_ieee_raw['DOI'] if 'DOI' in df_ieee_raw.columns else ""
    df_ieee['Database'] = 'IEEE'
    df_ieee = df_ieee[cols_to_keep]
else:
    df_ieee = pd.DataFrame(columns=cols_to_keep)

# ==========================================
# 3. Combine all data and deduplicate
# ==========================================
df_final = pd.concat([df_pubmed, df_ieee], ignore_index=True)
print(f"Total articles before cleaning: {len(df_final)}")

# Remove rows without abstracts
df_final = df_final.dropna(subset=['Abstract'])
df_final = df_final[df_final['Abstract'].astype(str).str.strip() != ""]

# Deduplicate by title
df_final['Title_Lower'] = df_final['Title'].astype(str).str.lower().str.strip()
df_final.drop_duplicates(subset=['Title_Lower'], keep='first', inplace=True)
df_final.drop(columns=['Title_Lower'], inplace=True)

output_file = "Final_Merged_Dataset.csv"
df_final.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"Done! Clean dataset saved with {len(df_final)} articles.")