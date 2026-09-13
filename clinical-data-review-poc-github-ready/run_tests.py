#!/usr/bin/env python
"""Project test runner with graceful Spark prerequisite detection."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys


def run(test_script: str, description: str) -> bool:
    print("\n" + "=" * 70)
    print(description)
    print("=" * 70)
    result = subprocess.run([sys.executable, test_script], text=True, check=False)
    return result.returncode == 0


def spark_ready() -> tuple[bool, str]:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        return False, "Python must be 3.10, 3.11, or 3.12."
    if importlib.util.find_spec("pyspark") is None:
        return False, "PySpark is not installed in this interpreter."
    if shutil.which("java") is None:
        return False, "Java is not on PATH."
    return True, "Spark prerequisites found."


def main() -> int:
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    print("=" * 70)
    print("HEALTHCARE DATA QUALITY POC TEST SUITE")
    print("=" * 70)
    print(f"Python: {sys.executable}")
    print(f"Project: {project_root}")

    smoke_ok = run(os.path.join("tests", "test_lite.py"), "Smoke tests")

    ready, reason = spark_ready()
    spark_ok = None
    if ready:
        spark_ok = run(os.path.join("tests", "test_quality_checks.py"), "Spark integration tests")
    else:
        print("\n" + "=" * 70)
        print("Spark integration tests skipped")
        print("=" * 70)
        print(reason)
        print("Install requirements and JDK 11/17 to run the full PySpark validation.")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Smoke tests: {'PASS' if smoke_ok else 'FAIL'}")
    print(f"Spark tests: {'PASS' if spark_ok else 'SKIPPED' if spark_ok is None else 'FAIL'}")
    return 0 if smoke_ok and (spark_ok is not False) else 1


if __name__ == "__main__":
    sys.exit(main())
