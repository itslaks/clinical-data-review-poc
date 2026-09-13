"""
query_drafting.py
------------------
Turns a flagged record into the short message that would be sent back
to the trial site. Rule-based / templated on purpose: no AI or external
API call is available on this machine, so this uses plain string
formatting instead. The function signature is deliberately simple
(one record in, one string out) so an LLM call could be substituted
here later without touching anything else in the pipeline.
"""

from pyspark.sql import functions as F
from pyspark.sql.types import StringType


def _get(row, key, default=""):
    try:
        value = row[key]
    except Exception:
        return default
    return default if value is None else value


def draft_query(row):
    """Build the query text for a single flagged record."""
    issue_type = _get(row, "issue_type", "quality_issue")
    issue_column = _get(row, "issue_column", _get(row, "field_name", "the flagged field"))
    record_id = _get(row, "record_id", _get(row, "id", "this row"))
    patient_id = _get(row, "patient_id", "unknown")

    if issue_type == "missing_value" or str(issue_type).startswith("missing_"):
        return (
            f"Please confirm and provide the missing value for "
            f"'{issue_column}' on record {record_id} "
            f"(patient {patient_id})."
        )
    if issue_type == "out_of_range" or "range" in str(issue_type):
        return (
            f"'{_get(row, 'field_name', issue_column)}' on record {record_id} "
            f"(patient {patient_id}) appears outside the expected range. "
            f"Please confirm the value or provide a correction."
        )
    if issue_type == "unit_mismatch" or str(issue_type).startswith("unit_mismatch"):
        return (
            f"'{_get(row, 'field_name', issue_column)}' on record {record_id} "
            f"(patient {patient_id}) has a unit mismatch. "
            f"Please confirm the unit and resubmit if needed."
        )
    if issue_type == "duplicate_measurement" or str(issue_type).startswith("duplicate_"):
        return (
            f"Duplicate records were detected for '{issue_column}'. "
            f"Please confirm which row should be retained for review."
        )
    if issue_type == "stale_data" or str(issue_type).startswith("stale_"):
        return (
            f"Record {record_id} appears older than the configured freshness rule. "
            f"Please confirm whether a newer value is available."
        )
    if str(issue_type).startswith("future_"):
        return f"Record {record_id} contains a future date in '{issue_column}'. Please verify the date."
    if str(issue_type).startswith("invalid_allowed_value_"):
        return f"Record {record_id} has an unexpected value in '{issue_column}'. Please confirm the valid healthcare code/value."
    if str(issue_type).startswith("invalid_format_"):
        return f"Record {record_id} has an invalid format in '{issue_column}'. Please verify the source-system code or identifier."
    if str(issue_type).startswith("invalid_date_order_"):
        return f"Record {record_id} has an end date before a start date. Please verify the encounter timeline."
    if str(issue_type).startswith("outlier_"):
        return f"Record {record_id} has an unusual value in '{issue_column}'. Please review the source value."
    return f"Please review record {record_id} for issue '{issue_type}'."


def add_drafted_queries(scored_df):
    """Apply draft_query() as a UDF across all flagged records."""
    draft_query_udf = F.udf(draft_query, StringType())
    return scored_df.withColumn(
        "drafted_query",
        draft_query_udf(F.struct(*[scored_df[c] for c in scored_df.columns]))
    )
