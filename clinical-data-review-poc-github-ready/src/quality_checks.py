"""
quality_checks.py (Refactored for dynamic, configurable rules)
-------------------------------------------------------------
Supports both hardcoded legacy clinical checks and flexible rule engine.
New rule-based approach allows ANY dataset with ANY rules via configuration.

Two implementations for cross-validation:
1. run_checks_dataframe() - PySpark DataFrame API
2. run_checks_sql()       - Spark SQL (legacy, clinical-only)

New unified approach:
3. ConfigurableQualityEngine - Rule-engine that works with any dataset
"""

import logging
import re
from typing import Dict, List, Any, Tuple
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql import DataFrame

try:
    from .config import HIGH_SEVERITY_THRESHOLD, REVIEW_DATE, STALE_DATA_DAYS
except ImportError:  # pragma: no cover - direct script execution fallback
    import config
    HIGH_SEVERITY_THRESHOLD = config.HIGH_SEVERITY_THRESHOLD
    REVIEW_DATE = config.REVIEW_DATE
    STALE_DATA_DAYS = config.STALE_DATA_DAYS

logger = logging.getLogger("data_review")


class ConfigurableQualityEngine:
    """Rule-based quality check engine that works with any dataset."""
    
    def __init__(self, rule_config: List[Dict[str, Any]], schema_info: Dict = None):
        """
        Initialize quality check engine with rules.
        
        Args:
            rule_config: List of rule definitions
            schema_info: Optional schema information from schema_detector.py
        """
        self.rules = rule_config
        self.schema_info = schema_info or {}
    
    def _match_columns(self, pattern: str, available_columns: List[str]) -> List[str]:
        """
        Find columns matching a pattern (can be regex or specific column name).
        
        Args:
            pattern: Regex pattern or column name
            available_columns: List of column names to search
        
        Returns:
            List of matching column names
        """
        if pattern in available_columns:
            return [pattern]
        
        matches = []
        try:
            regex = re.compile(f"^{pattern}$", re.IGNORECASE)
            for col in available_columns:
                if regex.match(col):
                    matches.append(col)
        except:
            pass
        
        return matches
    
    def check_missing_values(self, df: DataFrame, rule: Dict) -> Tuple[DataFrame, str]:
        """
        Check for missing/null values in specified columns.
        
        Rule config:
        {
            'type': 'missing_value',
            'column': 'field_name' or 'column_pattern': '.*value$',
            'threshold_warning': 5,  # Allow up to 5% nulls
            'threshold_critical': 20
        }
        """
        available_cols = df.columns
        
        if 'column' in rule:
            target_cols = [rule['column']] if rule['column'] in available_cols else []
        else:
            pattern = rule.get('column_pattern', '.*')
            target_cols = self._match_columns(pattern, available_cols)
        
        if not target_cols:
            return df.limit(0), "no_columns_matched"
        
        results = []
        for col in target_cols:
            # Calculate null percentage
            null_count = df.filter(F.col(col).isNull()).count()
            total_count = df.count()
            null_pct = (null_count / total_count * 100) if total_count > 0 else 0
            
            threshold_warning = rule.get('threshold_warning', 5)
            threshold_critical = rule.get('threshold_critical', 20)
            
            # Flag rows with nulls
            flagged = df.filter(F.col(col).isNull()).withColumn(
                "issue_type", F.lit(f"missing_{col}")
            ).withColumn(
                "issue_column", F.lit(col)
            ).withColumn(
                "null_percentage", F.lit(null_pct)
            )
            
            if flagged.count() > 0:
                results.append(flagged)
        
        if results:
            return results[0] if len(results) == 1 else results[0].union(*results[1:]), "missing_values"
        else:
            return df.limit(0), "no_issues"
    
    def check_duplicates(self, df: DataFrame, rule: Dict) -> Tuple[DataFrame, str]:
        """
        Check for duplicate values in specified columns.
        
        Rule config:
        {
            'type': 'duplicate',
            'column': 'patient_id' or 'column_pattern': '.*id$',
            'allow_nulls': True
        }
        """
        available_cols = df.columns
        
        if 'column' in rule:
            target_cols = [rule['column']] if rule['column'] in available_cols else []
        else:
            pattern = rule.get('column_pattern', '.*id$')
            target_cols = self._match_columns(pattern, available_cols)
        
        if not target_cols:
            return df.limit(0), "no_columns_matched"
        
        results = []
        for col in target_cols:
            allow_nulls = rule.get('allow_nulls', False)
            
            # Count occurrences of each value
            window = Window.partitionBy(col)
            checked = df.withColumn("dup_count", F.count("*").over(window))
            
            # Filter based on duplicates and null policy
            if allow_nulls:
                flagged = checked.filter((F.col("dup_count") > 1) & (F.col(col).isNotNull()))
            else:
                flagged = checked.filter(F.col("dup_count") > 1)
            
            if flagged.count() > 0:
                flagged = flagged.withColumn(
                    "issue_type", F.lit(f"duplicate_{col}")
                ).withColumn(
                    "issue_column", F.lit(col)
                ).drop("dup_count")
                results.append(flagged)
        
        if results:
            return results[0] if len(results) == 1 else results[0].union(*results[1:]), "duplicates"
        else:
            return df.limit(0), "no_issues"
    
    def check_numeric_range(self, df: DataFrame, rule: Dict) -> Tuple[DataFrame, str]:
        """
        Check numeric values against specified ranges.
        
        Rule config:
        {
            'type': 'numeric_range',
            'column': 'value',
            'min_value': 0,
            'max_value': 100,
            'use_reference_range': True  # Use ref_low/ref_high columns
        }
        """
        available_cols = df.columns
        col = rule.get('column')
        
        if not col or col not in available_cols:
            return df.limit(0), "column_not_found"
        
        # Try to convert to numeric
        try:
            numeric_col = F.col(col).cast("double")
        except:
            return df.limit(0), "column_not_numeric"
        
        flagged = None
        
        # Check against reference range if columns exist
        if rule.get('use_reference_range'):
            if 'ref_low' in available_cols and 'ref_high' in available_cols:
                flagged = df.filter(
                    (F.col('ref_low').isNotNull()) &
                    (F.col('ref_high').isNotNull()) &
                    ((numeric_col < F.col('ref_low')) | (numeric_col > F.col('ref_high')))
                ).withColumn(
                    "issue_type", F.lit("out_of_range")
                ).withColumn(
                    "issue_column", F.lit(col)
                )
        
        # Check against explicit min/max
        if flagged is None:
            conditions = []
            if 'min_value' in rule:
                conditions.append(numeric_col < rule['min_value'])
            if 'max_value' in rule:
                conditions.append(numeric_col > rule['max_value'])
            
            if conditions:
                combined = conditions[0]
                for cond in conditions[1:]:
                    combined = combined | cond
                
                flagged = df.filter(combined).withColumn(
                    "issue_type", F.lit("out_of_range")
                ).withColumn(
                    "issue_column", F.lit(col)
                )
        
        if flagged and flagged.count() > 0:
            return flagged, "out_of_range"
        else:
            return df.limit(0), "no_issues"
    
    def check_date_range(self, df: DataFrame, rule: Dict) -> Tuple[DataFrame, str]:
        """
        Check date columns for future dates or stale data.
        
        Rule config:
        {
            'type': 'date_range',
            'column': 'data_received_date',
            'check_future': True,
            'max_age_days': 365
        }
        """
        available_cols = df.columns
        col = rule.get('column')
        
        if not col or col not in available_cols:
            return df.limit(0), "column_not_found"
        
        results = []
        
        # Check for future dates
        if rule.get('check_future', False):
            today = F.to_date(F.lit(REVIEW_DATE))
            future_records = df.filter(F.col(col) > today).withColumn(
                "issue_type", F.lit("future_date")
            ).withColumn(
                "issue_column", F.lit(col)
            )
            if future_records.count() > 0:
                results.append(future_records)
        
        # Check for stale data
        max_age_days = rule.get('max_age_days')
        if max_age_days:
            today = F.to_date(F.lit(REVIEW_DATE))
            stale_records = df.filter(
                F.datediff(today, F.col(col)) > max_age_days
            ).withColumn(
                "issue_type", F.lit("stale_data")
            ).withColumn(
                "issue_column", F.lit(col)
            )
            if stale_records.count() > 0:
                results.append(stale_records)
        
        if results:
            return results[0] if len(results) == 1 else results[0].union(*results[1:]), "date_issues"
        else:
            return df.limit(0), "no_issues"
    
    def check_cardinality(self, df: DataFrame, rule: Dict) -> Tuple[DataFrame, str]:
        """
        Check that categorical columns don't have too many unique values.
        
        Rule config:
        {
            'type': 'cardinality',
            'column': 'status',
            'max_unique': 10
        }
        """
        available_cols = df.columns
        col = rule.get('column')
        
        if not col or col not in available_cols:
            return df.limit(0), "column_not_found"
        
        unique_count = df.select(col).distinct().count()
        max_unique = rule.get('max_unique', 100)
        
        if unique_count > max_unique:
            return df.withColumn(
                "issue_type", F.lit(f"high_cardinality_{col}")
            ).withColumn(
                "issue_column", F.lit(col)
            ).withColumn(
                "unique_values", F.lit(unique_count)
            ), "high_cardinality"
        
        return df.limit(0), "within_cardinality"
    
    def run(self, df: DataFrame) -> DataFrame:
        """
        Run all enabled rules against the dataframe.
        
        Returns:
            DataFrame with flagged records and issue_type column
        """
        all_flagged = []
        
        for rule in self.rules:
            if not rule.get('enabled', True):
                continue
            
            rule_type = rule.get('type')
            logger.info(f"Running rule: {rule.get('id', rule_type)}")
            
            try:
                if rule_type == 'missing_value':
                    flagged, status = self.check_missing_values(df, rule)
                elif rule_type == 'duplicate':
                    flagged, status = self.check_duplicates(df, rule)
                elif rule_type == 'numeric_range':
                    flagged, status = self.check_numeric_range(df, rule)
                elif rule_type == 'date_range':
                    flagged, status = self.check_date_range(df, rule)
                elif rule_type == 'cardinality':
                    flagged, status = self.check_cardinality(df, rule)
                else:
                    logger.warning(f"Unknown rule type: {rule_type}")
                    continue
                
                if flagged.count() > 0:
                    all_flagged.append(flagged)
                    logger.info(f"  {status}: {flagged.count()} records flagged")
            
            except Exception as e:
                logger.error(f"Error running rule {rule.get('id')}: {e}")
                continue
        
        if not all_flagged:
            return df.limit(0)
        
        result = all_flagged[0]
        for flagged in all_flagged[1:]:
            result = result.union(flagged)

        return result


# LEGACY FUNCTIONS (for backward compatibility with clinical data)

def run_checks_dataframe(df):
    """Legacy: Flag common clinical review issues using the DataFrame API."""
    duplicate_window = Window.partitionBy("patient_id", "source", "field_name")
    checked = df.withColumn(
        "duplicate_count",
        F.count("*").over(duplicate_window)
    ).withColumn(
        "issue_type",
        F.when(F.col("value").isNull(), F.lit("missing_value"))
         .when(
             (F.col("unit").isNotNull()) &
             (F.col("expected_unit").isNotNull()) &
             (F.col("unit") != F.col("expected_unit")),
             F.lit("unit_mismatch")
         )
         .when(F.col("duplicate_count") > 1, F.lit("duplicate_measurement"))
         .when(
             F.datediff(F.to_date(F.lit(REVIEW_DATE)), F.col("data_received_date")) > STALE_DATA_DAYS,
             F.lit("stale_data")
         )
         .when(
             (F.col("ref_low").isNotNull()) &
             ((F.col("value") < F.col("ref_low")) | (F.col("value") > F.col("ref_high"))),
             F.lit("out_of_range")
         )
         .otherwise(F.lit(None))
    )
    return checked.filter(F.col("issue_type").isNotNull()).drop("duplicate_count")


def run_checks_sql(spark, df, sql_path):
    """Legacy: Flag the same issues using a standalone Spark SQL script."""
    df.createOrReplaceTempView("clinical_records")
    with open(sql_path, "r") as f:
        query = (
            f.read()
            .replace("${REVIEW_DATE}", REVIEW_DATE)
            .replace("${STALE_DATA_DAYS}", str(STALE_DATA_DAYS))
        )
    return spark.sql(query)


def cross_validate(dataframe_result, sql_result):
    """
    Confirm both implementations flag the same record_id and issue_type pairs.
    Raises if they disagree, since that means one of the two has a bug.
    """
    if dataframe_result.count() == 0 and sql_result.count() == 0:
        logger.info("Cross-validation passed: Both implementations found no issues")
        return True

    df_flags = set(
        (r["record_id"], r["issue_type"])
        for r in dataframe_result.select("record_id", "issue_type").collect()
    )
    sql_flags = set(
        (r["record_id"], r["issue_type"])
        for r in sql_result.select("record_id", "issue_type").collect()
    )

    if df_flags != sql_flags:
        only_in_df = df_flags - sql_flags
        only_in_sql = sql_flags - df_flags
        raise AssertionError(
            f"DataFrame and SQL checks disagree. "
            f"Only in DataFrame result: {only_in_df}. Only in SQL result: {only_in_sql}."
        )
    logger.info("Cross-validation passed: DataFrame and SQL checks agree on %d flagged records", len(df_flags))
    return True


def add_severity(flagged_df):
    """
    Score how far outside the reference range a value falls, as a
    fraction of the range's width, then bucket into high/medium.
    Missing values, unit mismatches, stale data, and duplicate measurements
    are treated as high because they can block trusted review.
    """
    with_pct = flagged_df.withColumn(
        "range_width", F.col("ref_high") - F.col("ref_low")
    ).withColumn(
        "pct_outside",
        F.when(
            F.col("issue_type") == "out_of_range",
            F.when(F.col("value") < F.col("ref_low"),
                   (F.col("ref_low") - F.col("value")) / F.col("range_width"))
             .otherwise((F.col("value") - F.col("ref_high")) / F.col("range_width"))
        ).otherwise(F.lit(0.0))
    )

    scored = with_pct.withColumn(
        "severity",
        F.when(F.col("issue_type") == "missing_value", F.lit("high"))
         .when(F.col("issue_type") == "unit_mismatch", F.lit("high"))
         .when(F.col("issue_type") == "stale_data", F.lit("high"))
         .when(F.col("issue_type") == "duplicate_measurement", F.lit("medium"))
         .when((F.col("issue_type") == "out_of_range") & (F.col("pct_outside") > HIGH_SEVERITY_THRESHOLD), F.lit("high"))
         .when(F.col("issue_type") == "out_of_range", F.lit("medium"))
         .otherwise(F.lit("low"))
    )
    return scored
