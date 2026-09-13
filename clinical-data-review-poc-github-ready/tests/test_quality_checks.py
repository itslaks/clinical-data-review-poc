"""
test_quality_checks.py
-----------------------
A small set of sanity checks for the pipeline logic, written as plain
assertions rather than depending on pytest (kept dependency-light since
this needs to run on a locked-down laptop). Not exhaustive - just enough
to catch an obvious regression in the check logic or severity scoring.

Run from the project root:
    python3 tests/test_quality_checks.py
"""

import os
import sys
import subprocess
import shutil
import re


def ensure_java_home():
    """Set JAVA_HOME to the installed JDK if the environment is stale or missing."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home and os.path.exists(os.path.join(java_home, "bin", "java.exe")):
        os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ.get("PATH", "")
        return

    candidates = [
        r"C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot",
        r"C:\Program Files\Java\jdk-11.0.19",
        r"C:\Program Files\OpenJDK",
        r"C:\Program Files\Eclipse Adoptium",
    ]
    for base in candidates:
        if os.path.isdir(base):
            for root, dirs, _ in os.walk(base):
                java_exe = os.path.join(root, "bin", "java.exe")
                if os.path.exists(java_exe):
                    os.environ["JAVA_HOME"] = root
                    os.environ["PATH"] = os.path.join(root, "bin") + os.pathsep + os.environ.get("PATH", "")
                    return
    if shutil.which("java"):
        java_path = shutil.which("java")
        java_root = os.path.dirname(os.path.dirname(java_path))
        os.environ["JAVA_HOME"] = java_root
        os.environ["PATH"] = os.path.join(java_root, "bin") + os.pathsep + os.environ.get("PATH", "")


ensure_java_home()

# This project is validated on Python 3.10-3.12 with PySpark 3.5.x.
if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
    print("ERROR: Use Python 3.10, 3.11, or 3.12 for this PySpark POC.")
    print("Current interpreter: " + sys.executable)
    raise SystemExit(2)

# PySpark 3.5 works with Java 11 as well as Java 17.
# If Java is missing, Spark fails at startup with the exact "The system cannot find the path specified" message.
if shutil.which("java") is None:
    print("ERROR: Java is not installed or not on PATH for PySpark on Windows.")
    print("Spark needs a JDK/JRE available to start the JVM.")
    print()
    print("Fix:")
    print("  Install JDK 11 or JDK 17.")
    print("  Then restart PowerShell and verify with: java -version")
    print("  Optional: set JAVA_HOME to the Java install directory")
    raise SystemExit(2)

java_version = subprocess.run(["java", "-version"], capture_output=True, text=True)
java_text = (java_version.stderr or java_version.stdout or "").strip()
if not re.search(r"version\s+\"(1\.[89]|11|17|21)\b", java_text):
    print("ERROR: Unsupported Java version for this PySpark setup.")
    print("Detected Java output: " + (java_text[:200] or "<none>"))
    print("This project is validated with Java 11 or Java 17 and PySpark 3.5.")
    print("Install JDK 11 or JDK 17 and ensure java -version works before running Spark.")
    raise SystemExit(2)

# Suppress Spark initialization warnings on Windows
# (Spark looks for paths that don't exist during startup - this is harmless)
import warnings
warnings.filterwarnings('ignore')

# CRITICAL: Set PySpark environment variables BEFORE importing pyspark
# This fixes "Missing Python executable 'python3'" error on Windows
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['_JAVA_OPTIONS'] = '-Djava.awt.headless=true'

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)
os.environ["PYTHONPATH"] = SRC_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")

import io
from contextlib import redirect_stderr

print("Initializing Spark (this may take 1-2 minutes on first run)...")
print("=" * 60)

stderr_capture = io.StringIO()
with redirect_stderr(stderr_capture):
    from pyspark.sql import SparkSession
    from quality_checks import run_checks_dataframe, run_checks_sql, cross_validate, add_severity

SQL_PATH = os.path.join(os.path.dirname(SRC_DIR), "sql", "quality_checks.sql")


def make_test_df(spark):
    """A tiny, hand-built dataset with known expected outcomes."""
    rows = [
        # record_id, patient_id, source, field_name, value, unit, expected_unit, ref_low, ref_high, data_received_date
        ("T-01", "P-1", "Lab", "Glucose", 95.0, "mg/dL", "mg/dL", 70.0, 110.0, "2026-08-22"),   # clear
        ("T-02", "P-2", "Lab", "Glucose", None, "mg/dL", "mg/dL", 70.0, 110.0, "2026-08-22"),   # missing -> flagged, high
        ("T-03", "P-3", "Lab", "Glucose", 500.0, "mg/dL", "mg/dL", 70.0, 110.0, "2026-08-22"),  # way out of range -> flagged, high
        ("T-04", "P-4", "Lab", "Glucose", 115.0, "mg/dL", "mg/dL", 70.0, 110.0, "2026-08-22"),  # just out of range -> flagged, medium
        ("T-05", "P-5", "Lab", "Hemoglobin", 151.0, "g/L", "g/dL", 12.0, 16.0, "2026-08-22"),  # unit mismatch -> flagged, high
        ("T-06", "P-6", "Lab", "Creatinine", 1.0, "mg/dL", "mg/dL", 0.6, 1.3, "2026-08-01"),   # stale -> flagged, high
        ("T-07", "P-7", "Lab", "Sodium", 139.0, "mmol/L", "mmol/L", 135.0, 145.0, "2026-08-22"), # duplicate -> flagged, medium
        ("T-08", "P-7", "Lab", "Sodium", 140.0, "mmol/L", "mmol/L", 135.0, 145.0, "2026-08-22"), # duplicate -> flagged, medium
    ]
    columns = [
        "record_id", "patient_id", "source", "field_name", "value", "unit",
        "expected_unit", "ref_low", "ref_high", "data_received_date"
    ]
    df = spark.createDataFrame(rows, schema=columns)
    return df.selectExpr(
        "record_id",
        "patient_id",
        "source",
        "field_name",
        "value",
        "unit",
        "expected_unit",
        "ref_low",
        "ref_high",
        "to_date(data_received_date) as data_received_date",
    )


def run_tests():
    spark = SparkSession.builder.appName("QualityCheckTests").master("local[1]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    try:
        df = make_test_df(spark)

        # Test 1: exactly the expected 3 records get flagged, not the clear one
        flagged_df = run_checks_dataframe(df)
        flagged_ids = set(r["record_id"] for r in flagged_df.select("record_id").collect())
        assert flagged_ids == {"T-02", "T-03", "T-04", "T-05", "T-06", "T-07", "T-08"}, f"Unexpected flagged set: {flagged_ids}"
        print("PASS: DataFrame check flags the expected records")

        # Test 2: DataFrame and SQL implementations agree
        flagged_sql = run_checks_sql(spark, df, SQL_PATH)
        cross_validate(flagged_df, flagged_sql)
        print("PASS: DataFrame and SQL checks agree")

        # Test 3: severity assignment matches expectations
        scored = add_severity(flagged_df)
        severity_by_id = {r["record_id"]: r["severity"] for r in scored.select("record_id", "severity").collect()}
        assert severity_by_id["T-02"] == "high", "Missing value should always be high severity"
        assert severity_by_id["T-03"] == "high", "Value 500 vs range 70-110 should be high severity"
        assert severity_by_id["T-04"] == "medium", "Value 115 vs range 70-110 (just past boundary) should be medium"
        assert severity_by_id["T-05"] == "high", "Unit mismatch should be high severity"
        assert severity_by_id["T-06"] == "high", "Stale data should be high severity"
        assert severity_by_id["T-07"] == "medium", "Duplicate measurement should be medium severity"
        assert severity_by_id["T-08"] == "medium", "Duplicate measurement should be medium severity"
        print("PASS: Severity scoring matches expected buckets")

        print("\nAll tests passed.")

    finally:
        spark.stop()


if __name__ == "__main__":
    run_tests()
