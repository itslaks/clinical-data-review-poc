-- quality_checks.sql
-- ---------------------------------------------------------------------
-- Same logic as the PySpark DataFrame checks in quality_checks.py,
-- written as SQL against the `clinical_records` temp view.
-- Kept as a standalone .sql file (rather than a Python string) so it
-- reads and can be reviewed like any other SQL script, and so the two
-- implementations can be diffed independently if one needs to change.
--
-- Flags a record when it has a missing value, unit mismatch, duplicate
-- patient/source/field measurement, stale received date, or value outside
-- the given reference range.
-- ---------------------------------------------------------------------

WITH checked AS (
    SELECT
        record_id,
        patient_id,
        source,
        field_name,
        value,
        unit,
        expected_unit,
        ref_low,
        ref_high,
        data_received_date,
        COUNT(*) OVER (PARTITION BY patient_id, source, field_name) AS duplicate_count
    FROM clinical_records
),
flagged AS (
    SELECT
        record_id,
        patient_id,
        source,
        field_name,
        value,
        unit,
        expected_unit,
        ref_low,
        ref_high,
        data_received_date,
        CASE
            WHEN value IS NULL THEN 'missing_value'
            WHEN unit IS NOT NULL
                 AND expected_unit IS NOT NULL
                 AND unit <> expected_unit THEN 'unit_mismatch'
            WHEN duplicate_count > 1 THEN 'duplicate_measurement'
            WHEN datediff(to_date('${REVIEW_DATE}'), data_received_date) > ${STALE_DATA_DAYS} THEN 'stale_data'
            WHEN ref_low IS NOT NULL
                 AND (value < ref_low OR value > ref_high) THEN 'out_of_range'
        END AS issue_type
    FROM checked
)
SELECT *
FROM flagged
WHERE issue_type IS NOT NULL
ORDER BY record_id
