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
| Multi-source data review | CSV dataset with Lab, EDC, AE, encounter, claims, and generic upload support |
| Dataset understanding | Domain classifier detects healthcare, finance, inventory, web analytics, or generic data |
| Data quality checks | Missing values, ranges, stale/future dates, duplicates, unit mismatch, code formats, allowed values, outliers |
| Severity prioritization | High/medium severity assignment |
| Reviewer communication | Query drafting per flagged record |
| Operational dashboard | Streamlit command center with dashboard, profiler, rules, SQL evidence, metadata, and logs |
| Auditability | PySpark + Spark SQL validation |
| Export-ready output | CSV flagged records, summary CSV, dashboard image, run metadata JSON |

## Why this is the right scope

The goal is to demonstrate the core logic and user experience of a clinical review workflow, not to reproduce an entire enterprise platform. The project is intentionally focused on a realistic data-engineering slice that is easy to explain, easy to demo, and easy to extend for an L1 healthcare data engineer role.

## Demo framing

This project is a practical example of how a clinical review workflow can be brought into a faster, more transparent, and more measurable operating model using Python, Spark, and an executive dashboard.
