# Healthcare Data Quality Command Center

Streamlit + PySpark POC for healthcare data quality review.

## Run

```powershell
python -m pip install -r requirements.txt
python run_tests.py
streamlit run app.py
```

The full PySpark workflow requires Java JDK 11 or 17 on `PATH`.

## Best Demo

1. Select `clinical_records.csv`.
2. Keep the suggested Healthcare / Clinical template.
3. Choose `Clinical SQL validated`.
4. Run the workflow.
5. Show:
   - Review Dashboard
   - Schema Profiler
   - Rule Studio
   - SQL Evidence
   - Run Metadata

## Intelligent Features

- Detects likely dataset domain from columns and sample values.
- Suggests a matching rule template.
- Profiles column types, nulls, uniqueness, sample values, and semantic roles.
- Applies healthcare-native checks for identifiers, lab values, vitals, demographics, dates, claims, units, ICD/NPI-like fields, and outliers.
- Generates reviewer-friendly follow-up queries.
- Exports flagged records, summary reports, dashboard image, and metadata.

## Why It Fits A Fresher Data Engineer Profile

The code stays explainable while still showing real data engineering habits: schema validation, PySpark transformations, Spark SQL validation, modular Python, testable rule templates, and audit-oriented outputs.
