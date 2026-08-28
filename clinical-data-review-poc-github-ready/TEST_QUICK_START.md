# Quick Start

## Recommended local setup

```powershell
cd "C:\Users\2000189229\Documents\usecase\clinical-data-review-poc-main"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## Start the app

### Option 1: Interactive Configuration UI (Recommended for new users)

```powershell
cd "C:\Users\2000189229\Documents\usecase\clinical-data-review-poc-main"
$env:JAVA_HOME = "C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:SPARK_HOME = "$PWD\.venv\Lib\site-packages\pyspark"
$env:PYSPARK_PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:PYSPARK_DRIVER_PYTHON = $env:PYSPARK_PYTHON
& "$PWD\.venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501
```

Then:
1. Open http://localhost:8501
2. Click the **Configuration** tab
3. Upload your CSV (any format, any domain)
4. System auto-detects columns and suggests rules
5. Select a template (Clinical, Financial, Inventory, Web Analytics, Generic) or customize
6. Click "Run Quality Checks"
7. Review results in the dashboard

**NEW**: See [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) for complete workflow documentation.

### Option 2: Default Mode (Clinical workflow, backward compatible)

```powershell
& "$PWD\.venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501 -- --mode clinical
```

Your dataset must include the 10 clinical columns (see "Dataset Format" below).

### Option 3: Programmatic (Python code)

```python
from src.schema_detector import SchemaDetector
from src.rule_templates import RuleTemplates
from src.quality_checks import ConfigurableQualityEngine
import pandas as pd

# Load any CSV
df = pd.read_csv('data/your_file.csv')

# Auto-detect schema
detector = SchemaDetector()
detected = detector.detect_schema(df)

# Use a template
rules = RuleTemplates.financial_data()  # or clinical_data(), inventory_data(), etc.

# Run checks
engine = ConfigurableQualityEngine(rules)
results = engine.run_checks(df)
print(f"Found {len(results['issues'])} issues")
```

See [QUICK_START_ADVANCED.md](QUICK_START_ADVANCED.md) for more examples.

## What the application does

| Feature | Availability | Details |
|---------|--------------|---------|
| 📤 CSV Upload | Both modes | Upload any CSV or use demo data |
| 🔍 Schema Detection | **Config mode** | Auto-detects columns, types, semantic roles |
| 📋 Template Selection | **Config mode** | Choose from 5 domain templates or create custom |
| ✅ Quality Checks | Both modes | Runs configurable rules on your data |
| 🎯 Severity Scoring | Both modes | Ranks issues by impact |
| 🔍 Query Drafting | Both modes | Generates SQL for follow-up investigation |
| 📊 Executive Dashboard | Both modes | Professional HTML visualization |
| 💾 Export Reports | Both modes | CSV, PDF, PNG, JSON configs |

## Run validation tests

```powershell
& "$PWD\.venv\Scripts\python.exe" run_tests.py
```

Tests: Module imports, feature validation, PySpark integration, output generation

For detailed testing information, see [TESTING.md](TESTING.md).

## Dataset Format

### Configurable Mode (ANY Dataset)

✨ **NEW**: No schema required!
- Upload any CSV
- System auto-detects column types (numeric, date, categorical, ID, text)
- Select template or customize rules
- System adapts to your data

Example: Financial dataset with columns: `transaction_id`, `amount`, `date`, `account`, `category`
- ✅ Works! Auto-detects and suggests financial rules

### Default Mode (Clinical Workflow)

For backward compatibility, the original clinical workflow requires these 10 columns:

- `record_id` - Unique record identifier
- `patient_id` - Patient identifier
- `source` - Data source system
- `field_name` - Clinical field name
- `value` - Field value
- `unit` - Measurement unit
- `expected_unit` - Unit that should be used
- `ref_low` - Reference range low
- `ref_high` - Reference range high
- `data_received_date` - When data arrived

If using default mode and a file is missing required columns, the workflow will fail early with a clear validation message.

## Next Steps

- **First time?** → [QUICK_START_ADVANCED.md](QUICK_START_ADVANCED.md)
- **Need complete reference?** → [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md)
- **Want technical details?** → [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- **Troubleshooting?** → See README.md "Troubleshooting" section
