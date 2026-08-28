"""
main.py
-------
Clinical Data Review Agent - PySpark POC

Problem this addresses:
IQVIA's Clinical Data Review stage (part of their Clinical Data Analytics
Solutions platform) is, per IQVIA's own published figures, a manual
process that can take up to seven weeks per cycle. This POC automates
the first two steps of that process on a small sample:
  1. Detect data issues (missing values, out-of-range results)
  2. Draft the query text that would be sent back to the trial site

Everything here runs locally with no external API or LLM call, since
none is available on this machine. See README.md for the full write-up,
including what this does and doesn't prove.

Run from the project root:
    python3 src/main.py
"""

import logging
import os
import re
import shutil
import subprocess
import sys

import pandas as pd


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

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_pyspark = os.path.join(project_root, ".venv", "Lib", "site-packages", "pyspark")
if os.path.isdir(venv_pyspark):
    os.environ["SPARK_HOME"] = venv_pyspark

if sys.version_info[:2] != (3, 12):
    print("ERROR: This project is validated for Python 3.12.x (recommended: 3.12.2).")
    print("Current interpreter: " + sys.executable)
    print("PySpark startup can fail on unsupported Windows Python versions.")
    print()
    print("Fix:")
    print("  py -3.12 -m venv .venv")
    print("  .\\.venv\\Scripts\\python.exe -m pip install -U pip")
    print("  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    print("  .\\.venv\\Scripts\\python.exe src/main.py")
    raise SystemExit(2)

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

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SRC_DIR)

# PySpark executor subprocesses (even in local mode) start with their own
# Python path. They do not automatically inherit sys.path changes made in
# the driver process. Without this, the UDF in query_drafting.py fails on
# workers with "No module named 'query_drafting'". Setting PYTHONPATH
# before the SparkSession is created fixes it.
os.environ["PYTHONPATH"] = SRC_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")

from pyspark.sql import SparkSession

import config

if os.environ.get("CLINICAL_DATA_FILE"):
    config.INPUT_PATH = os.environ["CLINICAL_DATA_FILE"]
    config.OUTPUT_DIR = os.path.join(os.path.dirname(config.INPUT_PATH), "output")
    config.SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")

from ingest import load_records
from quality_checks import (
    run_checks_dataframe, run_checks_sql, cross_validate, add_severity,
    ConfigurableQualityEngine
)
from query_drafting import add_drafted_queries
from report import build_summary
from visualize import save_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clinical_data_review")


def print_stage(stage_name, message):
    print(f"\n[PHASE] {stage_name} - {message}")


def run_checks_with_config(records, rule_config=None, use_legacy=True):
    """
    Run quality checks using either:
    1. Legacy clinical rules (DataFrame + SQL cross-validation) if use_legacy=True
    2. Configurable rule engine if use_legacy=False and rule_config provided
    
    Args:
        records: PySpark DataFrame
        rule_config: List of rule definitions (for configurable mode)
        use_legacy: If True, use legacy clinical checks; if False, use configurable engine
    
    Returns:
        Flagged records DataFrame
    """
    if use_legacy:
        # Use original clinical checking logic
        return run_checks_dataframe(records)
    
    elif rule_config:
        # Use configurable quality engine
        engine = ConfigurableQualityEngine(rule_config)
        return engine.run(records)
    
    else:
        # Default to legacy if no config provided
        return run_checks_dataframe(records)


def main(rule_config=None):
    print_stage("START", "Initializing project environment and Spark session")
    spark = (
        SparkSession.builder
        .appName("ClinicalDataReviewAgent")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        print_stage("STEP 1/7", "Loading clinical records with schema validation")
        records = load_records(spark, config.INPUT_PATH)
        print(f"  Data rows ingested: {records.count()}")

        print_stage("STEP 2/7", "Running quality checks")
        use_legacy = rule_config is None
        if use_legacy:
            flagged_dataframe = run_checks_dataframe(records)
            print(f"  DataFrame-flagged records (legacy clinical rules): {flagged_dataframe.count()}")
        else:
            engine = ConfigurableQualityEngine(rule_config)
            flagged_dataframe = engine.run(records)
            print(f"  Records flagged (configurable rules): {flagged_dataframe.count()}")

        if use_legacy:
            print_stage("STEP 3/7", "Running Spark SQL quality checks")
            flagged_sql = run_checks_sql(spark, records, os.path.join(config.SQL_DIR, "quality_checks.sql"))
            print(f"  SQL-flagged records: {flagged_sql.count()}")

            print_stage("STEP 4/7", "Cross-validating DataFrame and SQL results")
            cross_validate(flagged_dataframe, flagged_sql)
            print("  Validation passed: both rule sets agree on flagged identifiers")
            
            # Use legacy results
            scored_input = flagged_dataframe
            next_phase = 5
        else:
            # Skip SQL validation for configurable mode, go straight to severity
            next_phase = 5
            scored_input = flagged_dataframe

        print_stage(f"STEP {next_phase}/7", "Assigning severity scores")
        scored = add_severity(scored_input)
        print(f"  Severity-scored rows: {scored.count()}")

        print_stage(f"STEP {next_phase+1}/7", "Drafting reviewer query text")
        flagged_with_query = add_drafted_queries(scored)
        print(f"  Query drafts generated: {flagged_with_query.count()}")

        print_stage(f"STEP {next_phase+2}/7", "Building summary report and writing final outputs")
        summary = build_summary(spark, flagged_with_query, os.path.join(config.SQL_DIR, "summary_report.sql"))
        total = records.count()
        n_flagged = flagged_with_query.count()
        logger.info("Total records reviewed : %d", total)
        logger.info("Flagged                : %d", n_flagged)
        logger.info("Clear                  : %d", total - n_flagged)

        print(f"  Total records reviewed: {total}")
        print(f"  Flagged records: {n_flagged}")
        print(f"  Clear records: {total - n_flagged}")

        print("\n=== Flagged records with drafted queries ===")
        flagged_with_query.select(
            "record_id", "patient_id", "source", "field_name", "issue_type", "severity", "drafted_query"
        ).orderBy("severity").show(truncate=False)

        print("=== Summary report (by source and severity) ===")
        summary.show(truncate=False)

        print_stage("EXPORT", "Writing flagged records to CSV for review export")
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        export_columns = [
            "record_id", "patient_id", "source", "field_name", "value", "unit",
            "expected_unit", "ref_low", "ref_high", "data_received_date",
            "issue_type", "severity", "drafted_query"
        ]
        export_df = pd.DataFrame([
            {k: v for k, v in row.asDict().items()}
            for row in flagged_with_query.select(*export_columns).collect()
        ])
        export_path = os.path.join(config.OUTPUT_DIR, "flagged_records", "flagged_records.csv")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        export_df.to_csv(export_path, index=False)
        print(f"  CSV export written to: {export_path}")
        logger.info("Flagged records written to %s", export_path)

        dashboard_path = save_dashboard(summary, flagged_with_query, config.OUTPUT_DIR)
        print(f"\n[VISUALIZATION] Dashboard saved to: {dashboard_path}")
        print("[COMPLETE] Clinical review workflow finished successfully")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
