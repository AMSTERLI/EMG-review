# Author: Bingle    Date: 2025-03-11
# Read PDFs from `PDF_Dataset`, extract plain text, and use an LLM
# to pull participant demographics into a structured CSV.

import pandas as pd
from openai import OpenAI
import json
import time
import os
import fitz  # PyMuPDF for reading PDFs
from tqdm import tqdm

# Configuration
client = OpenAI(
    api_key="sk-fuZPzEVQHmA3NDCzUbKMsKl7pyZqHsQrsfA5ibvfPjNatBdK",  # your API key
    base_url="https://api.ttk.homes/v1"  # proxy/base URL
)

MODEL_NAME = "gemini-2.5-pro-cli"

# 注意：请确保 input_file 是你实际采样的文件 (例如 'Sampled_900_Papers_Stratified.csv')
input_file = "Sampled_10_Papers.csv"  
output_file = "Extracted_Demographics_Results.csv"
pdf_folder = "PDF_Dataset"


def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"


def create_extraction_prompt(title, full_text):
    # 升级后的 Prompt：加入了国家、性别详情、年龄详情的提取要求
    return f"""You are an expert academic data extractor assisting with a systematic review on demographics in Electromyography (EMG) studies.

Your task is to read the full text and extract participant demographic information (Methods/Participants sections), as well as the country where the research was carried out.

Paper Title: {title}
---
Full Text:
{full_text}
---

Return strict JSON with these keys:
{{
    "sample_size": "Total number of human participants (integer) or null.",
    "country_of_research": "Country where the research/data collection was carried out based on author affiliations or explicit text, or 'Not reported'.",
    "reports_gender": "true or false",
    "gender_details": "Brief gender breakdown (e.g., '10 Male, 5 Female') or 'Not reported'.",
    "reports_age": "true or false",
    "age_details": "Brief age info (e.g., 'Mean 25.4, SD 2.1' or age range) or 'Not reported'.",
    "reports_race_or_ethnicity": "true or false",
    "race_ethnicity_details": "Brief breakdown of race/ethnicity if reported or 'Not reported'.",
    "reports_skin_color": "true or false",
    "skin_color_details": "Brief skin color/tone info if reported or 'Not reported'.",
    "extraction_notes": "Short note about location of demographic info or note if not human subjects."
}}"""

print("Loading dataset...")
df = pd.read_csv(input_file)

if os.path.exists(output_file):
    df_done = pd.read_csv(output_file)
    processed_ids = df_done['ID'].astype(str).tolist()
    print(f"Found existing output file. Resuming from {len(processed_ids)} processed articles...")
else:
    df_done = pd.DataFrame()
    processed_ids = []

results = []
save_interval = 5  # save every 5 records

print(f"Starting full-text extraction using {MODEL_NAME}...")
for index, row in tqdm(df.iterrows(), total=len(df)):
    doc_id = str(row.get('ID', index))
    if doc_id in processed_ids:
        continue

    title = str(row.get('Title', ''))

    # Build PDF path; replace '/' in IDs (e.g., DOIs) with '_'
    safe_doc_id = doc_id.replace('/', '_')
    pdf_path = os.path.join(pdf_folder, f"{safe_doc_id}.pdf")

    if not os.path.exists(pdf_path):
        row_data = row.to_dict()
        row_data['LLM_Status'] = 'PDF_Not_Found'
        results.append(row_data)
        continue

    full_text = extract_text_from_pdf(pdf_path)
    if full_text.startswith("Error"):
        row_data = row.to_dict()
        row_data['LLM_Status'] = 'PDF_Read_Error'
        results.append(row_data)
        continue

    # Truncate to first 100,000 characters to keep payload reasonable
    full_text = full_text[:100000]
    prompt = create_extraction_prompt(title, full_text)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output strict JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            result_str = response.choices[0].message.content
            result_json = json.loads(result_str)

            row_data = row.to_dict()
            row_data['LLM_Status'] = 'Success'
            
            # === 解析新增和原有的 JSON 字段 ===
            row_data['Sample_Size'] = result_json.get('sample_size', '')
            row_data['Country'] = result_json.get('country_of_research', '')
            
            row_data['Reports_Gender'] = result_json.get('reports_gender', False)
            row_data['Gender_Details'] = result_json.get('gender_details', '')
            
            row_data['Reports_Age'] = result_json.get('reports_age', False)
            row_data['Age_Details'] = result_json.get('age_details', '')
            
            row_data['Reports_Race'] = result_json.get('reports_race_or_ethnicity', False)
            row_data['Race_Details'] = result_json.get('race_ethnicity_details', '')
            
            row_data['Reports_Skin_Color'] = result_json.get('reports_skin_color', False)
            row_data['Skin_Color_Details'] = result_json.get('skin_color_details', '')
            
            row_data['Extraction_Notes'] = result_json.get('extraction_notes', '')

            results.append(row_data)

            # pause to avoid rate limits for large requests
            time.sleep(2)
            break

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print(f"\nFailed to process ID {doc_id}. Error: {e}")
                row_data = row.to_dict()
                row_data['LLM_Status'] = 'API_Error'
                results.append(row_data)

    # incremental save
    if len(results) >= save_interval:
        temp_df = pd.DataFrame(results)
        if os.path.exists(output_file):
            temp_df.to_csv(output_file, mode='a', header=False, index=False, encoding="utf-8-sig")
        else:
            temp_df.to_csv(output_file, mode='w', header=True, index=False, encoding="utf-8-sig")

        processed_ids.extend([str(r.get('ID')) for r in results])
        results = []

# save remaining results
if results:
    temp_df = pd.DataFrame(results)
    if os.path.exists(output_file):
        temp_df.to_csv(output_file, mode='a', header=False, index=False, encoding="utf-8-sig")
    else:
        temp_df.to_csv(output_file, mode='w', header=True, index=False, encoding="utf-8-sig")

print("\nAll done! Full-text extraction complete. Please check Extracted_Demographics_Results.csv.")