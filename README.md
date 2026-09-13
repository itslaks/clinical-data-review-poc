# Healthcare Data Quality Command Center

A fresher-friendly data engineering POC for clinical data review using **Python, PySpark, Spark SQL, pandas, and Streamlit**.

This project goes beyond basic data cleaning. It simulates a healthcare data-quality workflow where raw clinical records are checked, validated, scored by severity, converted into reviewer queries, and exported as audit-ready outputs.

## Why This Stands Out

Most data-cleaning POCs stop at removing nulls. This one shows a practical healthcare review flow:

- PySpark DataFrame checks for scalable validation.
- Spark SQL version of the same clinical checks for cross-validation.
- Intelligent domain detection for healthcare, finance, inventory, web analytics, and generic datasets.
- Healthcare-first rule templates for patient, encounter, lab, vitals, claims, medication, and demographic files.
- Schema profiling for unknown CSV files with confidence scores and matched domain signals.
- Reviewer-ready query text, not just cleaned data.
- Streamlit command center for dashboard, profiler, rule studio, SQL evidence, metadata, runtime log, and project story.

## Project Location

The working app is inside:

```powershell
cd clinical-data-review-poc-github-ready
```

## Quick Start

```powershell
cd clinical-data-review-poc-github-ready
python -m pip install -r requirements.txt
python run_tests.py
streamlit run app.py
```

Open the Streamlit URL shown in the terminal.

## Spark Prerequisites

The light tests and schema profiler work without Java. The full PySpark workflow needs:

- Python 3.10, 3.11, or 3.12
- Java JDK 11 or 17 on `PATH`
- Packages from `requirements.txt`

Verify Java:

```powershell
java -version
```

## What The App Does

1. Loads a CSV dataset.
2. Detects schema, column roles, likely business domain, and suggested rule template.
3. Runs healthcare quality checks:
   - missing patient/record/encounter/claim identifiers
   - missing clinical measurements
   - duplicate records
   - stale or future clinical dates
   - admission/discharge date order
   - out-of-range values using reference ranges
   - unit mismatches
   - invalid age, BMI, heart rate, and blood pressure ranges
   - invalid gender/status values
   - ICD/NPI-like format checks
   - negative healthcare amount checks
   - lab/vital outliers
4. Cross-validates the clinical rules with Spark SQL when the dataset matches the clinical schema.
5. Assigns severity.
6. Drafts reviewer queries.
7. Exports flagged records, summary CSV, dashboard image, and run metadata JSON.

## Main Files

- `app.py` - Streamlit command center.
- `src/main.py` - PySpark orchestration.
- `src/quality_checks.py` - Spark rules engine and clinical checks.
- `src/schema_detector.py` - CSV schema profiling.
- `src/rule_templates.py` - reusable rule templates.
- `sql/quality_checks.sql` - SQL implementation for validation.
- `data/clinical_records.csv` - demo healthcare dataset.

## Portfolio Talking Points

Use these in your project selection/interview:

- "I used PySpark window functions to find duplicate clinical measurements."
- "I wrote the same quality logic in Spark SQL and cross-validated it against the DataFrame output."
- "I added domain detection so the system recommends healthcare, finance, inventory, web analytics, or generic rules from the dataset itself."
- "I converted technical quality failures into reviewer-friendly clinical queries."
- "I added healthcare-native checks for lab values, vitals, claims, demographics, ICD/NPI-style fields, and encounter timelines."
- "I kept the project explainable for an L1 data engineer role while still showing production-style thinking."

## Outputs

Generated runtime outputs are written to:

- `output/flagged_records/flagged_records.csv`
- `output/summary_report.csv`
- `output/visualizations/clinical_review_dashboard.png`
- `output/run_metadata.json`

These files are ignored by Git.

## Production-Ready Practices Included

- Clear setup and testing commands.
- Runtime metadata for auditability.
- Sanitized upload filenames.
- Generated files ignored by Git.
- Light tests that work without Spark.
- Spark integration tests for full environments.
- Separated Python modules for ingestion, checks, query drafting, reports, schema detection, and visualization.
