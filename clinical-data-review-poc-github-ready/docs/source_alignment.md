# Source Alignment Notes

## Business context

This project is aligned to the real clinical data review challenge faced by trial operations teams and data managers.

Key themes from the target workflow:

- review diverse clinical data sources together
- identify missing, stale, duplicated, or out-of-range data
- prioritize high-risk records for intervention
- reduce manual review effort and duplication
- provide a clear operational view of data quality and follow-up actions

## POC mapping

| Business need | Implementation in this repo |
| --- | --- |
| Multi-source data review | CSV dataset with Lab, EDC, and AE-style records |
| Data quality checks | Missing values, out-of-range checks, stale records, duplicates, unit mismatch |
| Severity prioritization | High/medium severity assignment |
| Reviewer communication | Query drafting per flagged record |
| Operational dashboard | Streamlit executive review dashboard |
| Auditability | PySpark + Spark SQL validation |
| Export-ready output | CSV and PDF review pack |

## Why this is the right scope

The goal is to demonstrate the core logic and user experience of a clinical review workflow, not to reproduce an entire enterprise platform. The project is intentionally focused on a realistic data-engineering slice that is easy to explain, easy to demo, and easy to extend.

## Demo framing

This project is a practical example of how a clinical review workflow can be brought into a faster, more transparent, and more measurable operating model using Python, Spark, and an executive dashboard.
