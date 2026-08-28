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


def draft_query(row):
    """Build the query text for a single flagged record."""
    if row["issue_type"] == "missing_value":
        return (
            f"Please confirm and provide the missing value for "
            f"'{row['field_name']}' on record {row['record_id']} "
            f"(patient {row['patient_id']})."
        )
    if row["issue_type"] == "out_of_range":
        return (
            f"'{row['field_name']}' on record {row['record_id']} "
            f"(patient {row['patient_id']}) is recorded as {row['value']} "
            f"{row['unit'] or ''}, outside the expected range of "
            f"{row['ref_low']}-{row['ref_high']} {row['unit'] or ''}. "
            f"Please confirm the value or provide a correction."
        )
    if row["issue_type"] == "unit_mismatch":
        return (
            f"'{row['field_name']}' on record {row['record_id']} "
            f"(patient {row['patient_id']}) is recorded in {row['unit']}, "
            f"but the expected unit is {row['expected_unit']}. "
            f"Please confirm the unit and resubmit if needed."
        )
    if row["issue_type"] == "duplicate_measurement":
        return (
            f"Patient {row['patient_id']} has more than one "
            f"'{row['field_name']}' record from {row['source']}. "
            f"Please confirm which record should be used for review."
        )
    if row["issue_type"] == "stale_data":
        return (
            f"Record {row['record_id']} for patient {row['patient_id']} "
            f"was received on {row['data_received_date']}. "
            f"Please confirm whether a newer value is available."
        )
    return "Please review this record."


def add_drafted_queries(scored_df):
    """Apply draft_query() as a UDF across all flagged records."""
    draft_query_udf = F.udf(draft_query, StringType())
    return scored_df.withColumn(
        "drafted_query",
        draft_query_udf(F.struct([scored_df[c] for c in scored_df.columns]))
    )
