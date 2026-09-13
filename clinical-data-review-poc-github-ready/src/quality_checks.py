"""
quality_checks.py
-----------------
Spark-based quality checks for the healthcare data review POC.

The module intentionally has two layers:
1. Legacy clinical checks with a matching SQL implementation for validation.
2. A configurable rules engine that can run common checks on any CSV schema.
"""

from __future__ import annotations

import logging
import re
from functools import reduce
from typing import Any, Dict, Iterable, List, Tuple

from pyspark.sql import DataFrame, functions as F
from pyspark.sql.window import Window

try:
    from .config import HIGH_SEVERITY_THRESHOLD, REVIEW_DATE, STALE_DATA_DAYS
except ImportError:  # pragma: no cover - direct script execution fallback
    import config

    HIGH_SEVERITY_THRESHOLD = config.HIGH_SEVERITY_THRESHOLD
    REVIEW_DATE = config.REVIEW_DATE
    STALE_DATA_DAYS = config.STALE_DATA_DAYS

logger = logging.getLogger("clinical_data_review")


def _empty_like(df: DataFrame) -> DataFrame:
    empty = df.limit(0)
    for col_name in ["issue_type", "issue_column", "rule_id", "rule_severity", "metric_value"]:
        if col_name not in empty.columns:
            empty = empty.withColumn(col_name, F.lit(None).cast("string"))
    return empty


class ConfigurableQualityEngine:
    """Rule engine that applies common data-quality checks with PySpark."""

    SUPPORTED_RULES = {
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

    def __init__(self, rule_config: List[Dict[str, Any]], schema_info: Dict[str, Any] | None = None):
        self.rules = rule_config or []
        self.schema_info = schema_info or {}

    def _match_columns(self, pattern: str, available_columns: Iterable[str]) -> List[str]:
        columns = list(available_columns)
        if pattern in columns:
            return [pattern]

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            logger.warning("Invalid column pattern skipped: %s", pattern)
            return []

        return [col for col in columns if regex.fullmatch(col) or regex.search(col)]

    def _target_columns(self, rule: Dict[str, Any], df: DataFrame, default_pattern: str = ".*") -> List[str]:
        if rule.get("column"):
            return [rule["column"]] if rule["column"] in df.columns else []
        return self._match_columns(rule.get("column_pattern", default_pattern), df.columns)

    def _with_issue(self, df: DataFrame, rule: Dict[str, Any], issue_type: str, issue_column: str) -> DataFrame:
        return (
            df.withColumn("issue_type", F.lit(issue_type))
            .withColumn("issue_column", F.lit(issue_column))
            .withColumn("rule_id", F.lit(rule.get("id", issue_type)))
            .withColumn("rule_severity", F.lit(rule.get("severity", "warning")))
        )

    def _union_results(self, results: List[DataFrame], base_df: DataFrame) -> DataFrame:
        if not results:
            return _empty_like(base_df)
        return reduce(lambda left, right: left.unionByName(right, allowMissingColumns=True), results)

    def check_missing_values(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        total_count = df.count()
        if total_count == 0:
            return _empty_like(df), "empty_input"

        warning_threshold = float(rule.get("threshold_warning", 0))
        critical_threshold = float(rule.get("threshold_critical", 0))
        results: List[DataFrame] = []

        for col in self._target_columns(rule, df):
            null_count = df.filter(F.col(col).isNull() | (F.trim(F.col(col).cast("string")) == "")).count()
            null_pct = null_count / total_count * 100

            if null_count == 0 or null_pct < warning_threshold:
                continue

            severity = rule.get("severity", "warning")
            if critical_threshold and null_pct >= critical_threshold:
                severity = "critical"

            flagged = self._with_issue(
                df.filter(F.col(col).isNull() | (F.trim(F.col(col).cast("string")) == "")),
                {**rule, "severity": severity},
                f"missing_{col}",
                col,
            ).withColumn("metric_value", F.lit(round(null_pct, 2)))
            results.append(flagged)

        return self._union_results(results, df), "missing_values"

    def check_duplicates(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        results: List[DataFrame] = []
        for col in self._target_columns(rule, df, default_pattern=r".*id$|.*key$"):
            checked = df.withColumn("dup_count", F.count("*").over(Window.partitionBy(col)))
            if rule.get("allow_nulls", False):
                checked = checked.filter(F.col(col).isNotNull())

            flagged = checked.filter(F.col("dup_count") > 1)
            if flagged.take(1):
                results.append(
                    self._with_issue(flagged, rule, f"duplicate_{col}", col)
                    .withColumn("metric_value", F.col("dup_count"))
                    .drop("dup_count")
                )

        return self._union_results(results, df), "duplicates"

    def check_numeric_range(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        results: List[DataFrame] = []
        for col in self._target_columns(rule, df, default_pattern=r".*value.*|.*amount.*|.*count.*|.*quantity.*"):
            numeric_col = F.col(col).cast("double")
            conditions = []

            if rule.get("use_reference_range") and {"ref_low", "ref_high"}.issubset(df.columns):
                conditions.append(
                    F.col("ref_low").isNotNull()
                    & F.col("ref_high").isNotNull()
                    & ((numeric_col < F.col("ref_low")) | (numeric_col > F.col("ref_high")))
                )

            if rule.get("allow_negative") is False:
                conditions.append(numeric_col < 0)
            if "min_value" in rule:
                conditions.append(numeric_col < float(rule["min_value"]))
            if "max_value" in rule:
                conditions.append(numeric_col > float(rule["max_value"]))

            if not conditions:
                continue

            flagged = df.filter(reduce(lambda left, right: left | right, conditions))
            if flagged.take(1):
                results.append(self._with_issue(flagged, rule, f"range_check_{col}", col).withColumn("metric_value", numeric_col))

        return self._union_results(results, df), "numeric_range"

    def check_outlier(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        results: List[DataFrame] = []
        for col in self._target_columns(rule, df, default_pattern=r".*value.*|.*amount.*|.*duration.*|.*quantity.*"):
            numeric_col = F.col(col).cast("double")
            if "lower_bound" in rule and "upper_bound" in rule:
                lower, upper = float(rule["lower_bound"]), float(rule["upper_bound"])
            else:
                quantiles = df.select(numeric_col.alias(col)).na.drop().approxQuantile(col, [0.25, 0.75], 0.05)
                if len(quantiles) != 2:
                    continue
                q1, q3 = quantiles
                iqr = q3 - q1
                multiplier = float(rule.get("multiplier", 1.5))
                lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr

            flagged = df.filter((numeric_col < lower) | (numeric_col > upper))
            if flagged.take(1):
                results.append(self._with_issue(flagged, rule, f"outlier_{col}", col).withColumn("metric_value", numeric_col))

        return self._union_results(results, df), "outliers"

    def check_date_range(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        results: List[DataFrame] = []
        today = F.to_date(F.lit(rule.get("review_date", REVIEW_DATE)))

        for col in self._target_columns(rule, df, default_pattern=r".*date.*|.*time.*|.*timestamp.*|.*received.*"):
            date_col = F.to_date(F.col(col))
            if rule.get("check_future", False):
                future = df.filter(date_col > today)
                if future.take(1):
                    results.append(self._with_issue(future, rule, f"future_{col}", col))

            max_age_days = rule.get("max_age_days")
            if max_age_days is not None:
                stale = df.filter(F.datediff(today, date_col) > int(max_age_days))
                if stale.take(1):
                    results.append(self._with_issue(stale, rule, f"stale_{col}", col).withColumn("metric_value", F.datediff(today, date_col)))

        return self._union_results(results, df), "date_range"

    def check_cardinality(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        results: List[DataFrame] = []
        max_unique = int(rule.get("max_unique", 100))

        for col in self._target_columns(rule, df, default_pattern=r".*status.*|.*type.*|.*category.*|.*source.*"):
            unique_count = df.select(col).distinct().count()
            if unique_count > max_unique:
                results.append(
                    self._with_issue(df, rule, f"high_cardinality_{col}", col)
                    .withColumn("metric_value", F.lit(unique_count))
                )

        return self._union_results(results, df), "cardinality"

    def check_unit_mismatch(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        unit_cols = self._match_columns(rule.get("unit_column_pattern", r".*unit$"), df.columns)
        expected_cols = [col for col in df.columns if "expected" in col.lower() and "unit" in col.lower()]

        if "unit" in df.columns and "expected_unit" in df.columns:
            unit_cols = ["unit"]
            expected_cols = ["expected_unit"]

        results: List[DataFrame] = []
        for unit_col in unit_cols:
            expected_col = "expected_unit" if "expected_unit" in df.columns else (expected_cols[0] if expected_cols else None)
            if not expected_col or unit_col == expected_col:
                continue

            flagged = df.filter(
                F.col(unit_col).isNotNull()
                & F.col(expected_col).isNotNull()
                & (F.col(unit_col).cast("string") != F.col(expected_col).cast("string"))
            )
            if flagged.take(1):
                results.append(self._with_issue(flagged, rule, f"unit_mismatch_{unit_col}", unit_col))

        return self._union_results(results, df), "unit_mismatch"

    def check_allowed_values(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        allowed = [str(value).lower() for value in rule.get("allowed_values", [])]
        if not allowed:
            return _empty_like(df), "allowed_values_not_configured"

        results: List[DataFrame] = []
        for col in self._target_columns(rule, df, default_pattern=r".*status.*|.*gender.*|.*sex.*"):
            flagged = df.filter(F.col(col).isNotNull() & ~F.lower(F.col(col).cast("string")).isin(allowed))
            if flagged.take(1):
                results.append(self._with_issue(flagged, rule, f"invalid_allowed_value_{col}", col))
        return self._union_results(results, df), "allowed_values"

    def check_format(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        pattern = rule.get("regex")
        if not pattern:
            return _empty_like(df), "regex_not_configured"

        results: List[DataFrame] = []
        for col in self._target_columns(rule, df, default_pattern=r".*code.*|.*email.*|.*phone.*|.*npi.*|.*icd.*"):
            flagged = df.filter(F.col(col).isNotNull() & ~F.col(col).cast("string").rlike(pattern))
            if flagged.take(1):
                results.append(self._with_issue(flagged, rule, f"invalid_format_{col}", col))
        return self._union_results(results, df), "format_check"

    def check_date_order(self, df: DataFrame, rule: Dict[str, Any]) -> Tuple[DataFrame, str]:
        start_col = rule.get("start_column")
        end_col = rule.get("end_column")
        if not start_col or not end_col:
            start_matches = self._match_columns(rule.get("start_pattern", r".*admission.*|.*start.*|.*from.*"), df.columns)
            end_matches = self._match_columns(rule.get("end_pattern", r".*discharge.*|.*end.*|.*to.*"), df.columns)
            start_col = start_matches[0] if start_matches else None
            end_col = end_matches[0] if end_matches else None

        if not start_col or not end_col or start_col not in df.columns or end_col not in df.columns:
            return _empty_like(df), "date_columns_not_found"

        flagged = df.filter(F.to_date(F.col(end_col)) < F.to_date(F.col(start_col)))
        if flagged.take(1):
            return self._with_issue(flagged, rule, f"invalid_date_order_{start_col}_{end_col}", end_col), "date_order"
        return _empty_like(df), "date_order"

    def run(self, df: DataFrame) -> DataFrame:
        all_flagged: List[DataFrame] = []

        for rule in self.rules:
            if not rule.get("enabled", True):
                continue

            rule_type = rule.get("type")
            if rule_type not in self.SUPPORTED_RULES:
                logger.warning("Unknown rule type skipped: %s", rule_type)
                continue

            logger.info("Running configurable rule: %s", rule.get("id", rule_type))
            if rule_type == "missing_value":
                flagged, _ = self.check_missing_values(df, rule)
            elif rule_type == "duplicate":
                flagged, _ = self.check_duplicates(df, rule)
            elif rule_type == "numeric_range":
                flagged, _ = self.check_numeric_range(df, rule)
            elif rule_type == "date_range":
                flagged, _ = self.check_date_range(df, rule)
            elif rule_type == "cardinality":
                flagged, _ = self.check_cardinality(df, rule)
            elif rule_type == "unit_mismatch":
                flagged, _ = self.check_unit_mismatch(df, rule)
            elif rule_type == "allowed_values":
                flagged, _ = self.check_allowed_values(df, rule)
            elif rule_type == "format_check":
                flagged, _ = self.check_format(df, rule)
            elif rule_type == "date_order":
                flagged, _ = self.check_date_order(df, rule)
            else:
                flagged, _ = self.check_outlier(df, rule)

            if flagged.take(1):
                logger.info("Rule %s flagged %d rows", rule.get("id", rule_type), flagged.count())
                all_flagged.append(flagged)

        return self._union_results(all_flagged, df)


def run_checks_dataframe(df: DataFrame) -> DataFrame:
    """Legacy clinical checks using the PySpark DataFrame API."""
    duplicate_window = Window.partitionBy("patient_id", "source", "field_name")
    checked = (
        df.withColumn("duplicate_count", F.count("*").over(duplicate_window))
        .withColumn(
            "issue_type",
            F.when(F.col("value").isNull(), F.lit("missing_value"))
            .when(
                F.col("unit").isNotNull()
                & F.col("expected_unit").isNotNull()
                & (F.col("unit") != F.col("expected_unit")),
                F.lit("unit_mismatch"),
            )
            .when(F.col("duplicate_count") > 1, F.lit("duplicate_measurement"))
            .when(F.datediff(F.to_date(F.lit(REVIEW_DATE)), F.col("data_received_date")) > STALE_DATA_DAYS, F.lit("stale_data"))
            .when(
                F.col("ref_low").isNotNull()
                & F.col("ref_high").isNotNull()
                & ((F.col("value") < F.col("ref_low")) | (F.col("value") > F.col("ref_high"))),
                F.lit("out_of_range"),
            )
        )
    )
    return checked.filter(F.col("issue_type").isNotNull()).drop("duplicate_count")


def run_checks_sql(spark, df: DataFrame, sql_path: str) -> DataFrame:
    """Legacy clinical checks using Spark SQL for cross-validation."""
    df.createOrReplaceTempView("clinical_records")
    with open(sql_path, "r", encoding="utf-8") as handle:
        query = handle.read().replace("${REVIEW_DATE}", REVIEW_DATE).replace("${STALE_DATA_DAYS}", str(STALE_DATA_DAYS))
    return spark.sql(query)


def cross_validate(dataframe_result: DataFrame, sql_result: DataFrame) -> bool:
    """Assert DataFrame and SQL implementations flag the same clinical rows."""
    df_flags = {(r["record_id"], r["issue_type"]) for r in dataframe_result.select("record_id", "issue_type").collect()}
    sql_flags = {(r["record_id"], r["issue_type"]) for r in sql_result.select("record_id", "issue_type").collect()}

    if df_flags != sql_flags:
        raise AssertionError(f"DataFrame and SQL checks disagree. Only DF: {df_flags - sql_flags}. Only SQL: {sql_flags - df_flags}.")

    logger.info("Cross-validation passed: %d flagged record/issue pairs", len(df_flags))
    return True


def add_severity(flagged_df: DataFrame) -> DataFrame:
    """Add a normalized severity column for clinical and configurable results."""
    columns = set(flagged_df.columns)

    if "severity" in columns:
        return flagged_df

    if "rule_severity" in columns:
        return flagged_df.withColumn(
            "severity",
            F.when(F.lower(F.col("rule_severity")).isin("critical", "high"), F.lit("high"))
            .when(F.lower(F.col("rule_severity")).isin("info", "low"), F.lit("low"))
            .otherwise(F.lit("medium")),
        )

    if {"value", "ref_low", "ref_high"}.issubset(columns):
        with_pct = (
            flagged_df.withColumn("range_width", F.col("ref_high") - F.col("ref_low"))
            .withColumn(
                "pct_outside",
                F.when(
                    (F.col("issue_type") == "out_of_range") & (F.col("range_width") > 0) & (F.col("value") < F.col("ref_low")),
                    (F.col("ref_low") - F.col("value")) / F.col("range_width"),
                )
                .when(
                    (F.col("issue_type") == "out_of_range") & (F.col("range_width") > 0) & (F.col("value") > F.col("ref_high")),
                    (F.col("value") - F.col("ref_high")) / F.col("range_width"),
                )
                .otherwise(F.lit(0.0)),
            )
        )
    else:
        with_pct = flagged_df.withColumn("pct_outside", F.lit(0.0))

    return with_pct.withColumn(
        "severity",
        F.when(F.col("issue_type").isin("missing_value", "unit_mismatch", "stale_data"), F.lit("high"))
        .when(F.col("issue_type") == "duplicate_measurement", F.lit("medium"))
        .when((F.col("issue_type") == "out_of_range") & (F.col("pct_outside") > HIGH_SEVERITY_THRESHOLD), F.lit("high"))
        .when(F.col("issue_type") == "out_of_range", F.lit("medium"))
        .otherwise(F.lit("low")),
    )
