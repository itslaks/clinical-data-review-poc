"""
main.py
-------
Orchestrates the healthcare data quality review workflow.

Portfolio angle:
- PySpark ingestion and transformations.
- Spark SQL cross-validation for the clinical rule set.
- Configurable data-quality rules for non-clinical CSVs.
- Reviewer-friendly exports that show business usefulness.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
os.environ["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + os.environ.get("PYTHONPATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

import config
from ingest import RECORD_SCHEMA, load_records
from quality_checks import ConfigurableQualityEngine, add_severity, cross_validate, run_checks_dataframe, run_checks_sql
from query_drafting import add_drafted_queries
from report import build_summary
from rule_templates import RuleTemplates
from schema_detector import SchemaDetector
from visualize import save_dashboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("clinical_data_review")


def ensure_java_home() -> None:
    """Best-effort Java discovery for Windows laptops."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home and Path(java_home, "bin", "java.exe").exists():
        os.environ["PATH"] = str(Path(java_home, "bin")) + os.pathsep + os.environ.get("PATH", "")
        return

    candidates = [
        Path(r"C:\Program Files\OpenLogic"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Java"),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for java_exe in base.glob("**/bin/java.exe"):
            os.environ["JAVA_HOME"] = str(java_exe.parents[1])
            os.environ["PATH"] = str(java_exe.parent) + os.pathsep + os.environ.get("PATH", "")
            return


def validate_runtime() -> None:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        raise SystemExit("Use Python 3.10, 3.11, or 3.12 for this PySpark POC.")

    ensure_java_home()
    if shutil.which("java") is None:
        raise SystemExit("Java is required for PySpark. Install JDK 11 or 17 and verify with: java -version")

    java_version = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
    java_text = (java_version.stderr or java_version.stdout or "").strip()
    if not re.search(r"version\s+\"(1\.[89]|11|17|21)\b", java_text):
        raise SystemExit(f"Unsupported Java version for this POC. Detected: {java_text[:200] or '<none>'}")


def print_stage(stage_name: str, message: str) -> None:
    print(f"\n[PHASE] {stage_name} - {message}")


def load_generic_records(spark, path: str):
    logger.info("Loading generic CSV from %s", path)
    df = spark.read.option("header", True).option("inferSchema", True).csv(path)
    if df.count() == 0:
        raise ValueError(f"No records loaded from {path}.")
    return df


def looks_like_clinical_schema(columns: List[str]) -> bool:
    required = {field.name for field in RECORD_SCHEMA.fields}
    return required.issubset(set(columns))


def classify_dataset(path: str) -> Dict[str, Any]:
    preview = pd.read_csv(path, nrows=1000)
    detector = SchemaDetector(preview)
    detector.detect_schema()
    return detector.classify_domain()


def normalize_flagged_for_export(flagged_df, clinical_mode: bool):
    if clinical_mode:
        ordered = [
            "record_id",
            "patient_id",
            "source",
            "field_name",
            "value",
            "unit",
            "expected_unit",
            "ref_low",
            "ref_high",
            "data_received_date",
            "issue_type",
            "severity",
            "drafted_query",
        ]
        return flagged_df.select(*[col for col in ordered if col in flagged_df.columns])

    front = ["issue_type", "issue_column", "rule_id", "severity", "drafted_query"]
    ordered = [col for col in front if col in flagged_df.columns] + [col for col in flagged_df.columns if col not in front]
    return flagged_df.select(*ordered)


def build_generic_summary(flagged_df):
    group_cols = ["issue_type", "severity"]
    if "source" in flagged_df.columns:
        group_cols.insert(0, "source")
    else:
        flagged_df = flagged_df.withColumn("source", flagged_df["issue_column"])
        group_cols.insert(0, "source")
    return flagged_df.groupBy(*group_cols).count().withColumnRenamed("count", "flagged_count")


def run_pipeline(dataset_path: str | None = None, rule_config: List[Dict[str, Any]] | None = None, force_mode: str = "auto") -> Dict[str, Any]:
    validate_runtime()

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("ClinicalDataReviewAgent").master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    input_path = dataset_path or os.environ.get("CLINICAL_DATA_FILE") or config.INPUT_PATH
    output_dir = Path(os.environ.get("REVIEW_OUTPUT_DIR") or config.OUTPUT_DIR)
    domain_profile = classify_dataset(input_path)
    clinical_mode = force_mode == "clinical"

    try:
        print_stage("START", "Initializing Spark session")
        if force_mode == "configurable" or rule_config:
            records = load_generic_records(spark, input_path)
            clinical_mode = False
        else:
            preview = spark.read.option("header", True).csv(input_path)
            clinical_mode = looks_like_clinical_schema(preview.columns)
            records = load_records(spark, input_path) if clinical_mode else load_generic_records(spark, input_path)

        total = records.count()
        print(f"  Data rows ingested: {total}")
        print(f"  Columns detected: {', '.join(records.columns)}")

        print_stage("CHECKS", "Running quality checks")
        if clinical_mode and not rule_config:
            flagged = run_checks_dataframe(records)
            print(f"  DataFrame flagged records: {flagged.count()}")

            print_stage("SQL", "Cross-validating with Spark SQL")
            flagged_sql = run_checks_sql(spark, records, str(Path(config.SQL_DIR) / "quality_checks.sql"))
            cross_validate(flagged, flagged_sql)
            print("  Validation passed: PySpark DataFrame checks match Spark SQL checks")
        else:
            if not rule_config:
                mapped_domain = "clinical" if domain_profile["domain"] == "clinical" else domain_profile["domain"]
                rule_config = RuleTemplates.get_template(mapped_domain)["rules"]
                print(f"  Auto-selected template: {mapped_domain} (confidence {domain_profile['confidence']})")
            flagged = ConfigurableQualityEngine(rule_config).run(records)
            print(f"  Configurable rules flagged records: {flagged.count()}")

        print_stage("SCORING", "Assigning severity and drafting reviewer questions")
        scored = add_severity(flagged)
        flagged_with_query = add_drafted_queries(scored)
        n_flagged = flagged_with_query.count()

        summary = (
            build_summary(spark, flagged_with_query, str(Path(config.SQL_DIR) / "summary_report.sql"))
            if clinical_mode
            else build_generic_summary(flagged_with_query)
        )

        print(f"  Total records reviewed: {total}")
        print(f"  Flagged records: {n_flagged}")
        print(f"  Clear records: {max(total - n_flagged, 0)}")

        print_stage("EXPORT", "Writing review-ready outputs")
        export_dir = output_dir / "flagged_records"
        export_dir.mkdir(parents=True, exist_ok=True)
        export_df = pd.DataFrame([row.asDict() for row in normalize_flagged_for_export(flagged_with_query, clinical_mode).collect()])
        export_path = export_dir / "flagged_records.csv"
        export_df.to_csv(export_path, index=False)

        summary_df = pd.DataFrame([row.asDict() for row in summary.collect()])
        summary_path = output_dir / "summary_report.csv"
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(summary_path, index=False)

        dashboard_path = save_dashboard(summary, flagged_with_query, str(output_dir))
        metadata_path = output_dir / "run_metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "input_path": input_path,
                    "detected_domain": domain_profile,
                    "clinical_sql_validated": bool(clinical_mode and not rule_config),
                    "total_records": total,
                    "flagged_records": n_flagged,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  CSV export written to: {export_path}")
        print(f"  Summary written to: {summary_path}")
        print(f"  Metadata written to: {metadata_path}")
        print(f"  Dashboard saved to: {dashboard_path}")
        print("[COMPLETE] Healthcare data review workflow finished successfully")

        return {
            "input_path": input_path,
            "clinical_mode": clinical_mode,
            "total": total,
            "flagged": n_flagged,
            "clear": max(total - n_flagged, 0),
            "export_path": str(export_path),
            "summary_path": str(summary_path),
            "metadata_path": str(metadata_path),
            "dashboard_path": dashboard_path,
        }
    finally:
        spark.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run healthcare data quality review POC")
    parser.add_argument("--input", default=None, help="CSV path to review")
    parser.add_argument("--mode", choices=["auto", "clinical", "configurable"], default="auto")
    parser.add_argument("--rules", default=None, help="Optional JSON file containing configurable rules")
    return parser.parse_args()


def main(rule_config: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    return run_pipeline(rule_config=rule_config)


if __name__ == "__main__":
    args = parse_args()
    rules = None
    if args.rules:
        with open(args.rules, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            rules = loaded.get("rules", loaded if isinstance(loaded, list) else [])
    run_pipeline(dataset_path=args.input, rule_config=rules, force_mode=args.mode)
