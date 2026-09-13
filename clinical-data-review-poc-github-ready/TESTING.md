# Testing Guide

Run these commands from this folder:

```powershell
cd clinical-data-review-poc-github-ready
python -m pip install -r requirements.txt
python run_tests.py
```

## Test Levels

### Smoke Tests

```powershell
python tests/test_lite.py
```

These tests do not need Java or Spark. They validate:

- schema detection
- rule-template compatibility
- sample clinical dataset shape

### Spark Integration Tests

```powershell
python tests/test_quality_checks.py
```

These tests need:

- Python 3.10, 3.11, or 3.12
- PySpark from `requirements.txt`
- Java JDK 11 or 17 on `PATH`

They validate:

- PySpark DataFrame clinical quality checks
- Spark SQL clinical quality checks
- DataFrame-vs-SQL cross-validation
- severity scoring

If Spark prerequisites are missing, `run_tests.py` skips the integration test and explains what to install.
