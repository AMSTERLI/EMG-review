#Author:Bingle    Date: 2026-03-10
#Ten articles were randomly selected from the merged CSV file.
#===========================================

import pandas as pd

# 1. Read the full dataset
df = pd.read_csv("Final_Merged_Dataset.csv")

# 2. Randomly sample 10 articles
df_sampled = df.sample(n=10, random_state=600)

# 3. Save sampling results
output_file = "Sampled_10_Papers.csv"
df_sampled.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"✅ Successfully randomly sampled {len(df_sampled)} articles! File saved as: {output_file}")