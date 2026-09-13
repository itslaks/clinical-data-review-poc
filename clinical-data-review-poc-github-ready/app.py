from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.rule_templates import RuleTemplates
from src.schema_detector import SchemaDetector

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_DIR = PROJECT_ROOT / "src" / "configurations"
FLAGGED_CSV = OUTPUT_DIR / "flagged_records" / "flagged_records.csv"
SUMMARY_CSV = OUTPUT_DIR / "summary_report.csv"
METADATA_JSON = OUTPUT_DIR / "run_metadata.json"

CLINICAL_COLUMNS = {
    "record_id",
    "patient_id",
    "source",
    "field_name",
    "value",
    "unit",
    "expected_unit",
    "ref_low",
    "ref_high",
    "data_received_date",
}

st.set_page_config(page_title="Healthcare Data Quality Command Center", page_icon="H-DQ", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #f8fafc; color: #0f172a; }
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1320px; }
      [data-testid="stSidebar"] { background: #0f172a; }
      [data-testid="stSidebar"] * { color: #e2e8f0; }
      [data-testid="stMetricValue"] { font-size: 1.85rem; color: #0f172a; }
      .hero {
        padding: 1.2rem 1.3rem;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        background: linear-gradient(135deg, #ffffff 0%, #eef6ff 48%, #ecfdf5 100%);
        margin-bottom: 1rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, .06);
      }
      .hero h1 { margin: 0; font-size: 2rem; color: #0f172a; }
      .hero p { margin: .35rem 0 0; color: #334155; }
      .pill {
        display: inline-block;
        padding: .28rem .55rem;
        border-radius: 999px;
        background: #dbeafe;
        color: #1e40af;
        font-weight: 700;
        font-size: .78rem;
        margin-right: .35rem;
      }
      .note {
        border-left: 4px solid #2563eb;
        padding: .7rem .9rem;
        background: #eff6ff;
        color: #1e3a8a;
        border-radius: 4px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_filename(name: str) -> str:
    stem = Path(name).name
    return re.sub(r"[^A-Za-z0-9_.-]", "_", stem)[:90] or "uploaded.csv"


def available_datasets() -> list[Path]:
    DATA_DIR.mkdir(exist_ok=True)
    return sorted(DATA_DIR.glob("*.csv"))


def load_preview(path: Path, rows: int = 200) -> pd.DataFrame:
    return pd.read_csv(path, nrows=rows)


def looks_clinical(df: pd.DataFrame) -> bool:
    return CLINICAL_COLUMNS.issubset(set(df.columns))


def load_outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    flagged = pd.read_csv(FLAGGED_CSV) if FLAGGED_CSV.exists() else pd.DataFrame()
    summary = pd.read_csv(SUMMARY_CSV) if SUMMARY_CSV.exists() else pd.DataFrame()
    return flagged, summary


def load_metadata() -> dict:
    if not METADATA_JSON.exists():
        return {}
    return json.loads(METADATA_JSON.read_text(encoding="utf-8"))


def detect_domain(df: pd.DataFrame) -> dict:
    detector = SchemaDetector(df)
    detector.detect_schema()
    return detector.classify_domain()


def parse_metrics(log_text: str) -> dict[str, int]:
    values = {}
    for key, pattern in {
        "total": r"Total records reviewed:\s*(\d+)",
        "flagged": r"Flagged records:\s*(\d+)",
        "clear": r"Clear records:\s*(\d+)",
    }.items():
        match = re.search(pattern, log_text)
        values[key] = int(match.group(1)) if match else 0
    return values


def write_rules_file(template_id: str) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    template = RuleTemplates.get_template(template_id)
    path = CONFIG_DIR / "active_streamlit_rules.json"
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return path


def run_review(dataset_path: Path, mode: str, template_id: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYSPARK_PYTHON"] = sys.executable
    env["PYSPARK_DRIVER_PYTHON"] = sys.executable
    env["REVIEW_OUTPUT_DIR"] = str(OUTPUT_DIR)

    cmd = [sys.executable, "src/main.py", "--input", str(dataset_path), "--mode", mode]
    if mode == "configurable":
        cmd.extend(["--rules", str(write_rules_file(template_id))])

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, text=True, capture_output=True, timeout=420)
    return result.returncode, (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")


def render_schema_profile(df: pd.DataFrame) -> None:
    detector = SchemaDetector(df)
    schema = detector.detect_schema()
    domain = detector.classify_domain()
    score_rows = [
        {
            "domain": name,
            "score": details["score"],
            "matched_signals": ", ".join(details["matched"][:8]),
        }
        for name, details in domain["scores"].items()
    ]
    st.markdown(
        f"<span class='pill'>Detected: {domain['domain'].replace('_', ' ').title()}</span>"
        f"<span class='pill'>Confidence: {domain['confidence']:.0%}</span>",
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

    profile = pd.DataFrame(
        [
            {
                "column": name,
                "type": info["inferred_type"],
                "role": info["semantic_role"],
                "confidence": round(info["confidence"], 2),
                "nulls": info["null_count"],
                "null_pct": round(info["null_ratio"] * 100, 2),
                "unique": info["unique_count"],
                "sample": ", ".join(info["sample_values"][:3]),
            }
            for name, info in schema.items()
        ]
    )
    st.dataframe(profile, use_container_width=True, hide_index=True)

    type_counts = profile["type"].value_counts().rename_axis("type").reset_index(name="columns")
    fig = px.bar(type_counts, x="type", y="columns", title="Detected Column Types", color="type")
    st.plotly_chart(fig, use_container_width=True)


def render_review_dashboard(flagged: pd.DataFrame, summary: pd.DataFrame) -> None:
    if flagged.empty:
        st.info("No output yet. Choose a dataset from the sidebar and run the review workflow.")
        return

    if "severity" not in flagged.columns:
        flagged["severity"] = "unknown"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Flagged rows", len(flagged))
    col2.metric("High priority", int((flagged["severity"].str.lower() == "high").sum()))
    col3.metric("Issue types", flagged["issue_type"].nunique() if "issue_type" in flagged else 0)
    col4.metric("Columns reviewed", flagged["issue_column"].nunique() if "issue_column" in flagged else len(flagged.columns))

    chart_col, table_col = st.columns([1, 1.4])
    with chart_col:
        sev = flagged["severity"].fillna("unknown").str.lower().value_counts().rename_axis("severity").reset_index(name="rows")
        fig = px.pie(sev, names="severity", values="rows", hole=0.42, title="Issue Severity Mix")
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        if not summary.empty:
            st.dataframe(summary, use_container_width=True, hide_index=True)
        else:
            st.dataframe(flagged.head(20), use_container_width=True, hide_index=True)

    st.subheader("Reviewer Work Queue")
    display_cols = [col for col in ["severity", "issue_type", "issue_column", "record_id", "patient_id", "source", "field_name", "drafted_query"] if col in flagged.columns]
    st.dataframe(flagged[display_cols] if display_cols else flagged, use_container_width=True, hide_index=True)

    st.download_button("Download flagged records CSV", data=FLAGGED_CSV.read_bytes(), file_name="flagged_records.csv", mime="text/csv")


def render_rule_studio(template_id: str) -> None:
    template = RuleTemplates.get_template(template_id)
    rules = pd.DataFrame(template["rules"])
    st.markdown(f"**{template['name']}**: {template['description']}")
    st.dataframe(rules.fillna(""), use_container_width=True, hide_index=True)

    supported = {"missing_value", "duplicate", "numeric_range", "date_range", "cardinality", "unit_mismatch", "outlier", "allowed_values", "format_check", "date_order"}
    rules["implemented"] = rules["type"].isin(supported)
    fig = px.bar(rules.groupby(["type", "implemented"], as_index=False).size(), x="type", y="size", color="implemented", title="Rules Implemented in Spark Engine")
    st.plotly_chart(fig, use_container_width=True)


def render_sql_evidence() -> None:
    st.markdown(
        "<div class='note'>For the clinical workflow, the same checks run once in PySpark DataFrame code and once in Spark SQL. Matching results prove the transformation logic is consistent.</div>",
        unsafe_allow_html=True,
    )
    sql_path = PROJECT_ROOT / "sql" / "quality_checks.sql"
    st.code(sql_path.read_text(encoding="utf-8"), language="sql")


def render_project_story() -> None:
    st.markdown(
        """
        **Why this stands out for a fresher healthcare data engineer**

        This is not only a null-cleaning demo. It shows a small but realistic clinical data review pipeline:
        PySpark for scalable checks, SQL for validation, Python for orchestration, schema profiling for unknown files,
        and reviewer-ready query text for business users.

        **Skills demonstrated:** CSV ingestion, schema validation, window functions, Spark SQL, configurable rule templates,
        quality scoring, exports, Streamlit dashboards, and healthcare-domain reasoning.
        """
    )


datasets = available_datasets()
uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if uploaded is not None:
    target = DATA_DIR / safe_filename(uploaded.name)
    target.write_bytes(uploaded.getvalue())
    st.sidebar.success(f"Uploaded {target.name}")

datasets = available_datasets()
dataset_names = [path.name for path in datasets]
selected_name = st.sidebar.selectbox("Dataset", dataset_names, index=dataset_names.index("clinical_records.csv") if "clinical_records.csv" in dataset_names else 0)
selected_path = DATA_DIR / selected_name
preview_df = load_preview(selected_path)
domain_profile = detect_domain(preview_df)

template_options = RuleTemplates.list_templates()
template_ids = [item["id"] for item in template_options]
suggested_template = "clinical" if domain_profile["domain"] == "clinical" else domain_profile["domain"]
suggested_index = template_ids.index(suggested_template) if suggested_template in template_ids else template_ids.index("generic")
st.sidebar.markdown("### Dataset Intelligence")
st.sidebar.metric("Detected domain", domain_profile["domain"].replace("_", " ").title())
st.sidebar.metric("Confidence", f"{domain_profile['confidence']:.0%}")
if domain_profile.get("reason"):
    st.sidebar.caption("Signals: " + ", ".join(domain_profile["reason"]))

template_id = st.sidebar.selectbox("Rule template", template_ids, index=suggested_index, format_func=lambda value: next(item["name"] for item in template_options if item["id"] == value))
mode_label = st.sidebar.radio("Execution mode", ["Auto detect", "Clinical SQL validated", "Configurable Spark rules"])
mode = {"Auto detect": "auto", "Clinical SQL validated": "clinical", "Configurable Spark rules": "configurable"}[mode_label]

st.markdown(
    """
    <div class="hero">
      <h1>Healthcare Data Quality Command Center</h1>
      <p>Domain-aware PySpark + SQL review workflow for healthcare data quality, reviewer queries, and audit-ready exports.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not looks_clinical(preview_df):
    st.warning("This file does not match the clinical schema. Use Configurable Spark rules or Auto detect.")

if st.sidebar.button("Run review workflow", type="primary", use_container_width=True):
    with st.spinner("Running PySpark workflow..."):
        code, log = run_review(selected_path, mode, template_id)
    st.session_state["last_log"] = log
    st.session_state["last_metrics"] = parse_metrics(log)
    if code == 0:
        st.sidebar.success("Workflow complete")
        st.rerun()
    else:
        st.sidebar.error("Workflow failed. See Runtime Log tab.")

flagged_df, summary_df = load_outputs()
metadata = load_metadata()
top_a, top_b, top_c = st.columns(3)
top_a.metric("Selected dataset", selected_name)
top_b.metric("Auto domain", domain_profile["domain"].replace("_", " ").title())
top_c.metric("Suggested template", RuleTemplates.get_template(template_id)["name"])

tabs = st.tabs(["Review Dashboard", "Schema Profiler", "Rule Studio", "SQL Evidence", "Run Metadata", "Runtime Log", "Project Story"])

with tabs[0]:
    render_review_dashboard(flagged_df, summary_df)

with tabs[1]:
    st.subheader(f"Schema Profile: {selected_name}")
    st.dataframe(preview_df.head(30), use_container_width=True, hide_index=True)
    render_schema_profile(preview_df)

with tabs[2]:
    render_rule_studio(template_id)

with tabs[3]:
    render_sql_evidence()

with tabs[4]:
    st.json(metadata or {"message": "Run the workflow to generate metadata."})

with tabs[5]:
    st.code(st.session_state.get("last_log", "No workflow run in this Streamlit session yet."), language="text")

with tabs[6]:
    render_project_story()
