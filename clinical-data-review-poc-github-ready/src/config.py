"""
config.py
---------
Central place for settings the pipeline depends on: file paths and the
severity threshold. Kept separate from the check logic so a reviewer
can change a threshold or a path without touching quality_checks.py.
"""

import os

# Paths are relative to the project root (where main.py is run from)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(BASE_DIR, "data", "clinical_records.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SQL_DIR = os.path.join(BASE_DIR, "sql")

# A flagged value counts as HIGH severity if it falls this far outside
# the reference range, expressed as a fraction of the range's width.
# e.g. 0.4 means "40% past the boundary or worse".
HIGH_SEVERITY_THRESHOLD = 0.4

# Fixed review date keeps the POC deterministic during demos.
REVIEW_DATE = "2026-08-23"
STALE_DATA_DAYS = 14
