#!/usr/bin/env python
"""Fast smoke tests that do not require Java or a Spark runtime."""

from __future__ import annotations

import os
import sys

import pandas as pd

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)


def check(name, fn):
    try:
        fn()
        print(f"PASS: {name}")
        return True
    except Exception as exc:
        print(f"FAIL: {name} -> {exc}")
        return False


def test_schema_detector():
    from schema_detector import SchemaDetector

    df = pd.DataFrame(
        {
            "patient_id": ["P1", "P2", "P3"],
            "visit_date": ["2026-08-01", "2026-08-02", "2026-08-03"],
            "glucose_value": [90, 180, None],
            "site": ["Mumbai", "Delhi", "Mumbai"],
        }
    )
    schema = SchemaDetector(df).detect_schema()
    assert schema["patient_id"]["semantic_role"] == "id"
    assert schema["visit_date"]["inferred_type"] == "date"
    assert schema["glucose_value"]["semantic_role"] == "measurement"
    domain = SchemaDetector(df).classify_domain()
    assert domain["domain"] == "clinical"
    assert domain["confidence"] > 0


def test_rule_templates_are_supported():
    from rule_templates import RuleTemplates

    supported = {
        "missing_value",
        "duplicate",
        "numeric_range",
        "date_range",
        "cardinality",
        "unit_mismatch",
        "outlier",
        "allowed_values",
        "format_check",
        "date_order",
    }
    for template in RuleTemplates.all_templates().values():
        unsupported = {rule["type"] for rule in template["rules"] if rule.get("enabled", True)} - supported
        assert not unsupported, f"{template['name']} has unsupported enabled rules: {unsupported}"


def test_sample_dataset_exists():
    project_root = os.path.dirname(SRC_DIR)
    data_path = os.path.join(project_root, "data", "clinical_records.csv")
    assert os.path.exists(data_path)
    df = pd.read_csv(data_path)
    required = {"record_id", "patient_id", "source", "field_name", "value", "data_received_date"}
    assert required.issubset(df.columns)
    assert len(df) >= 10


def main():
    print("=" * 70)
    print("LIGHT SMOKE TESTS - no Java or Spark required")
    print("=" * 70)
    results = [
        check("schema detector", test_schema_detector),
        check("rule templates match engine", test_rule_templates_are_supported),
        check("sample clinical dataset", test_sample_dataset_exists),
    ]
    print("=" * 70)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
