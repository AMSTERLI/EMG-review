# Demographic Relevance Sensitivity Analysis

Input cohort: `PDF_Dataset/Sampled_Papers_Stratified.csv` (`n = 377`).

Classifier: DeepSeek API, model `deepseek-v4-pro`.

Classification variable:

- `0`: Demographic variables are not part of the research question.
- `1`: Demographic variables are used only as eligibility or control factors.
- `2`: Sex/gender, age, race/ethnicity, skin phenotype, or related physiological differences are primary exposures or comparison factors.

Classification results:

| demographic_relevance | Count | Percentage |
|---:|---:|---:|
| 0 | 291 | 77.19% |
| 1 | 72 | 19.10% |
| 2 | 14 | 3.71% |

Sensitivity analysis excluding class 2 papers:

| Metric | Original | After excluding class 2 | Absolute change |
|---|---:|---:|---:|
| Sex/gender reporting | 330/377 (87.53%) | 316/363 (87.05%) | -0.48 percentage points |
| Age reporting | 339/377 (89.92%) | 325/363 (89.53%) | -0.39 percentage points |
| Race/ethnicity or skin reporting | 10/377 (2.65%) | 8/363 (2.20%) | -0.45 percentage points |

Class 2 papers only:

| Metric | Class 2 reporting |
|---|---:|
| Sex/gender reporting | 14/14 (100.00%) |
| Age reporting | 14/14 (100.00%) |
| Race/ethnicity or skin reporting | 2/14 (14.29%) |

Interpretation: excluding studies whose primary objective involved demographic or related physiological comparisons did not materially change the direction of the original reporting-rate findings. Reporting remained high for sex/gender and age and sparse for race/ethnicity or skin-related variables.

Note: This is an LLM-assisted classification and should be manually reviewed before manuscript submission, especially the 14 class 2 records and any borderline class 1/class 2 decisions.

Article-level category lists are provided in `demographic_relevance_0_articles.csv`, `demographic_relevance_1_articles.csv`, and `demographic_relevance_2_articles.csv`.
