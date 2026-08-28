-- summary_report.sql
-- ---------------------------------------------------------------------
-- Aggregation report over the flagged records (`flagged_records` temp
-- view, produced after severity has been assigned). Two things this
-- shows deliberately:
--   1. A GROUP BY rollup of flag counts by source and severity -
--      the kind of summary a data manager would actually want to see.
--   2. A window function (RANK) to order flagged records within each
--      severity band by how far outside range they are, so the most
--      urgent record in each band is easy to find.
-- ---------------------------------------------------------------------

SELECT
    source,
    severity,
    COUNT(*) AS flagged_count,
    RANK() OVER (PARTITION BY severity ORDER BY COUNT(*) DESC) AS rank_within_severity
FROM flagged_records
GROUP BY source, severity
ORDER BY severity, flagged_count DESC
