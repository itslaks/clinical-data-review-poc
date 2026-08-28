# Sample Dataset

`clinical_records.csv` is the execution dataset for this POC. It is simulated and contains no real patient data.

## Columns

| Column | Meaning |
| --- | --- |
| `record_id` | Unique row identifier |
| `patient_id` | Simulated patient identifier |
| `source` | Data source such as EDC, Lab, or AE |
| `field_name` | Clinical field being reviewed |
| `value` | Reported value |
| `unit` | Unit received from the source |
| `expected_unit` | Unit expected by the study rule |
| `ref_low` | Lower expected range |
| `ref_high` | Upper expected range |
| `data_received_date` | Date the record was received |

## Issue Types Covered

| Issue type | Example in dataset |
| --- | --- |
| `missing_value` | Missing creatinine, potassium, weight, or AE onset date |
| `out_of_range` | Low hemoglobin, high AE severity grade, low sodium, high blood pressure |
| `unit_mismatch` | Hemoglobin in `g/L` where `g/dL` is expected |
| `stale_data` | Creatinine record received more than 14 days before the fixed review date |
| `duplicate_measurement` | Two glucose records for the same patient/source/field combination |

The fixed review date is configured in `src/config.py` so results stay consistent during demos.
