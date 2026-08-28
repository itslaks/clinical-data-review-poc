"""
ingest.py
---------
Reads the raw CSV into a PySpark DataFrame using an explicit schema.
Explicit schemas matter here: if a source system changes a column type
or drops a field, this fails loudly at ingestion instead of quietly
producing wrong results three steps later.
"""

import logging
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, DateType

logger = logging.getLogger("clinical_data_review")

RECORD_SCHEMA = StructType([
    StructField("record_id", StringType(), True),
    StructField("patient_id", StringType(), True),
    StructField("source", StringType(), True),
    StructField("field_name", StringType(), True),
    StructField("value", DoubleType(), True),
    StructField("unit", StringType(), True),
    StructField("expected_unit", StringType(), True),
    StructField("ref_low", DoubleType(), True),
    StructField("ref_high", DoubleType(), True),
    StructField("data_received_date", DateType(), True),
])


def load_records(spark, path):
    """Read the clinical records CSV into a schema-enforced DataFrame."""
    logger.info("Loading records from %s", path)
    df = (
        spark.read
        .option("header", True)
        .schema(RECORD_SCHEMA)
        .csv(path)
    )
    count = df.count()
    logger.info("Loaded %d records", count)
    if count == 0:
        raise ValueError(f"No records loaded from {path} - check the file path and header row.")
    return df
