"""
report.py
---------
Runs the summary_report.sql aggregation against the flagged records,
so the pipeline ends with something a data manager could actually read
at a glance: counts by source and severity, ranked.
"""

import logging

logger = logging.getLogger("clinical_data_review")


def build_summary(spark, flagged_with_query_df, sql_path):
    flagged_with_query_df.createOrReplaceTempView("flagged_records")
    with open(sql_path, "r") as f:
        query = f.read()
    logger.info("Running summary report")
    return spark.sql(query)
