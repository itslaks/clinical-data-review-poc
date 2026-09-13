# Quick Start

```powershell
cd clinical-data-review-poc-github-ready
python -m pip install -r requirements.txt
python run_tests.py
streamlit run app.py
```

## App Tabs

- **Review Dashboard**: flagged records, severity mix, reviewer work queue, CSV download.
- **Schema Profiler**: pandas-based profile for uploaded CSVs.
- **Rule Studio**: clinical/generic rule templates and implementation status.
- **SQL Evidence**: Spark SQL used to cross-check clinical PySpark logic.
- **Runtime Log**: latest pipeline log.
- **Project Story**: short explanation for interviews/project selection.

## Best Demo Flow

1. Open the app with `streamlit run app.py`.
2. Keep `clinical_records.csv` selected.
3. Choose `Clinical SQL validated`.
4. Run the review workflow.
5. Show the reviewer queue and SQL Evidence tab.

This flow highlights PySpark, SQL, Python orchestration, and healthcare data-quality thinking.
