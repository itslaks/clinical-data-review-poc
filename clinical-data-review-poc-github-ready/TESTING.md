# Testing and Setup Guide

This project is validated on Python 3.12.x with Java 11 and PySpark 3.5.x.

## 1) Create the environment

```powershell
cd "C:\Users\2000189229\Documents\usecase\clinical-data-review-poc-main"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## 2) Verify module imports (NEW MODULES)

All new modules should import successfully:

```powershell
python -c "
from src.schema_detector import SchemaDetector
from src.rule_templates import RuleTemplates
from src.config_ui import render_full_configuration_wizard
from src.quality_checks import ConfigurableQualityEngine
print('[OK] All modules import successfully')
print('[OK] 5 templates available:', list(RuleTemplates.get_available_templates().keys()))
"
```

Expected output:
```
[OK] All modules import successfully
[OK] 5 templates available: ['Clinical Data', 'Financial Data', 'Inventory Data', 'Web Analytics', 'Generic Data']
```

## 3) Start the dashboard

### Default Mode (Clinical workflow, original behavior)
```powershell
cd "C:\Users\2000189229\Documents\usecase\clinical-data-review-poc-main"
$env:JAVA_HOME = "C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:SPARK_HOME = "$PWD\.venv\Lib\site-packages\pyspark"
$env:PYSPARK_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:PYSPARK_DRIVER_PYTHON = $env:PYSPARK_PYTHON
& "$PWD\.venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501
```

### Configurable Mode (Interactive UI with schema detection)
```powershell
cd "C:\Users\2000189229\Documents\usecase\clinical-data-review-poc-main"
$env:JAVA_HOME = "C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:SPARK_HOME = "$PWD\.venv\Lib\site-packages\pyspark"
$env:PYSPARK_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:PYSPARK_DRIVER_PYTHON = $env:PYSPARK_PYTHON
& "$PWD\.venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501 -- --mode configurable
```

Open:
- http://localhost:8501
- Navigate to **Configuration** tab for interactive rule setup

See [QUICK_START_ADVANCED.md](QUICK_START_ADVANCED.md) for detailed workflow examples.

## 4) Run validation tests

### Smoke tests (Core imports and features)

```powershell
& "$PWD\.venv\Scripts\python.exe" tests/test_lite.py
```

Tests: Module imports, environment detection, basic functionality

### Quality checks tests (Clinical workflow validation)

```powershell
& "$PWD\.venv\Scripts\python.exe" tests/test_quality_checks.py
```

Tests: Clinical rule engine, PySpark validation, output generation

### Full combined runner

```powershell
& "$PWD\.venv\Scripts\python.exe" run_tests.py
```

Runs all tests in sequence with summary reporting

## 5) Test the new configurable engine

### Programmatic usage (Python)

```python
from src.schema_detector import SchemaDetector
from src.rule_templates import RuleTemplates
from src.quality_checks import ConfigurableQualityEngine
import pandas as pd

# Load your CSV
df = pd.read_csv('data/your_file.csv')

# Auto-detect schema
detector = SchemaDetector()
schema = detector.detect_schema(df)
print("Detected columns:", schema)

# Load a template
rules = RuleTemplates.financial_data()

# Run quality checks
engine = ConfigurableQualityEngine(rules)
results = engine.run_checks(df)
print("Issues found:", len(results['issues']))
```

### Interactive UI (Streamlit)

1. Upload CSV to dashboard
2. Click "Configuration" tab
3. Review auto-detected schema
4. Select template or customize rules
5. Save configuration to JSON
6. Run checks

See [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) for complete reference.

## Required dataset schema

The uploaded CSV must include the following columns:

- `record_id`
- `patient_id`
- `source`
- `field_name`
- `value`
- `unit`
- `expected_unit`
- `ref_low`
- `ref_high`
- `data_received_date`

If a file does not contain these fields, the workflow will stop early with a clear validation message rather than failing later in the processing pipeline.

## Troubleshooting

### Java and Spark startup issues on Windows

Use the exact environment setup above. The project is tuned for Java 11 and Python 3.12.2.

```powershell
$env:JAVA_HOME = "C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

### “The system cannot find the path specified”

This is normally caused by stale Java environment variables or unsupported Python versions. Ensure:

- Python is 3.12.x
- Java is installed and on PATH
- `JAVA_HOME` matches the real JDK location
- `SPARK_HOME` points to the installed PySpark package inside `.venv`

### “Missing Python executable 'python3'”

Set both environment variables before starting Spark:

```powershell
$env:PYSPARK_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:PYSPARK_DRIVER_PYTHON = $env:PYSPARK_PYTHON
```

## Project outputs

The runtime workflow writes review output to:

- `output/flagged_records/flagged_records.csv`
- `output/visualizations/clinical_review_dashboard.png`
- `output/clinical_review_exec_summary.csv`
- `output/clinical_review_exec_summary.pdf`

These outputs are generated during runtime and should stay out of Git history via `.gitignore`.
