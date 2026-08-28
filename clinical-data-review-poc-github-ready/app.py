from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"
FLAGGED_DIR = OUTPUT_DIR / "flagged_records"

st.set_page_config(
    page_title="Clinical Review Command Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        :root {
            --slate-950: #020817;
            --slate-900: #0f172a;
            --indigo-600: #4f46e5;
            --cyan-500: #06b6d4;
            --emerald-500: #10b981;
            --amber-500: #f59e0b;
            --rose-500: #f43f5e;
            --gray-200: #e2e8f0;
            --gray-400: #94a3b8;
        }
        html, body, [data-testid='stAppViewContainer'] {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #020817 0%, #0f172a 18%, #111827 40%, #1e293b 100%);
            color: var(--gray-200);
        }
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        [data-testid='stSidebar'] {
            background: rgba(15, 23, 42, 0.82);
            border-right: 1px solid rgba(148, 163, 184, 0.25);
        }
        .hero {
            background: linear-gradient(135deg, rgba(79, 70, 229, 0.22), rgba(6, 182, 212, 0.18), rgba(16, 185, 129, 0.18));
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 24px;
            padding: 1.5rem 1.6rem;
            box-shadow: 0 20px 35px rgba(15, 23, 42, 0.35);
            margin-bottom: 1.25rem;
        }
        .kpi {
            background: rgba(15, 23, 42, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 1rem 1rem 0.8rem;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.25);
        }
        .subtle {
            color: var(--gray-400);
            font-size: 0.88rem;
        }
        .stTabs [role='tablist'] button {
            font-weight: 600;
        }
        .stDataFrame { background: rgba(15, 23, 42, 0.44); }
    </style>
    """,
    unsafe_allow_html=True,
)

SEVERITY_COLORS = {"high": "#f43f5e", "medium": "#f59e0b", "low": "#22c55e", "unknown": "#64748b"}


def list_and_prepare_datasets():
    files = sorted(DATA_DIR.glob("*.csv")) if DATA_DIR.exists() else []
    choices = [f.name for f in files]
    return choices


def parse_pipeline_log(log_text: str):
    match_total = re.search(r"Total records reviewed\s*:\s*(\d+)", log_text)
    match_flagged = re.search(r"Flagged\s*:\s*(\d+)", log_text)
    match_clear = re.search(r"Clear\s*:\s*(\d+)", log_text)
    total = int(match_total.group(1)) if match_total else 0
    flagged = int(match_flagged.group(1)) if match_flagged else 0
    clear = int(match_clear.group(1)) if match_clear else max(total - flagged, 0)
    return {"total": total, "flagged": flagged, "clear": clear}


def run_pipeline(dataset_path: str):
    try:
        env = os.environ.copy()
        env["PYSPARK_PYTHON"] = sys.executable
        env["PYSPARK_DRIVER_PYTHON"] = sys.executable
        env["CLINICAL_DATA_FILE"] = dataset_path
        env["JAVA_HOME"] = os.environ.get("JAVA_HOME") or r"C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot"
        env["PATH"] = os.path.join(env["JAVA_HOME"], "bin") + os.pathsep + env.get("PATH", "")

        process = subprocess.Popen(
            [sys.executable, "src/main.py"],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        output_lines = []
        if process.stdout is not None:
            for line in iter(process.stdout.readline, ""):
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    yield line
        return_code = process.wait()
        yield f"\n[FINAL_EXIT_CODE] {return_code}"
        yield "\n[PROCESS_COMPLETE]"
        return return_code, "\n".join(output_lines)
    except Exception as exc:  # pragma: no cover
        yield str(exc)
        return 1, str(exc)


def locate_flagged_csv():
    csv_dir = OUTPUT_DIR / "flagged_records"
    files = sorted(csv_dir.glob("*.csv")) if csv_dir.exists() else []
    return files[-1] if files else None


def load_flagged_data():
    csv_path = locate_flagged_csv()
    if csv_path is None:
        return pd.DataFrame(), None
    df = pd.read_csv(csv_path)
    if "severity" not in df.columns:
        df["severity"] = "unknown"
    df["severity"] = df["severity"].fillna("unknown").str.lower()
    return df, csv_path


def export_pdf(df: pd.DataFrame, summary: pd.DataFrame, path: str):
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("Clinical Data Review Executive Summary", styles["Title"]))
    story.append(Spacer(1, 18))

    summary_table = [["Source", "Severity", "Flagged Count"]]
    for _, row in summary.iterrows():
        summary_table.append([str(row.get("source", "")), str(row.get("severity", "")), str(row.get("flagged_count", 0))])

    table = Table(summary_table, colWidths=[140, 140, 130])
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.8, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 18))

    top_rows = df.head(10).copy()
    if not top_rows.empty:
        top_rows = top_rows[["record_id", "patient_id", "source", "issue_type", "severity"]].fillna("-")
        story.append(Paragraph("Priority flagged records", styles["Heading2"]))
        top_table = [["Record", "Patient", "Source", "Issue", "Severity"]]
        for _, row in top_rows.iterrows():
            top_table.append([str(row["record_id"]), str(row["patient_id"]), str(row["source"]), str(row["issue_type"]), str(row["severity"])])
        top_pdf_table = Table(top_table, colWidths=[65, 80, 65, 150, 70])
        top_pdf_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c3aed")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.7, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))
        story.append(top_pdf_table)

    doc = SimpleDocTemplate(path, pagesize=A4)
    doc.build(story)


if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = "Ready"
if "pipeline_log" not in st.session_state:
    st.session_state.pipeline_log = ""
if "metrics" not in st.session_state:
    st.session_state.metrics = {"total": 0, "flagged": 0, "clear": 0}
if "dataset_name" not in st.session_state:
    st.session_state.dataset_name = "clinical_records.csv"

available_datasets = list_and_prepare_datasets()
selected_dataset = st.sidebar.selectbox(
    "Select a dataset",
    options=available_datasets if available_datasets else ["clinical_records.csv"],
    index=available_datasets.index(st.session_state.dataset_name) if st.session_state.dataset_name in available_datasets else 0,
)
st.session_state.dataset_name = selected_dataset

uploaded_file = st.sidebar.file_uploader("Or upload a new clinical dataset", type=["csv"])

st.sidebar.markdown("---")
st.sidebar.caption("Environment")
st.sidebar.code(f"Python: {sys.executable}\nJava: {os.environ.get('JAVA_HOME') or 'Not set'}")

st.markdown(
    """
    <div class="hero">
        <h1 style='margin:0; color:white;'>Clinical Review Command Center</h1>
        <p style='margin-top:0.6rem; margin-bottom:0; color:#dbeafe; font-size:1.06rem;'>Operational oversight for data-quality triage, issue prioritization, and reviewer query generation.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Workflow controls")
    if st.button("Run review workflow", use_container_width=True, type="primary"):
        target_dataset = selected_dataset
        if uploaded_file is not None:
            target_path = DATA_DIR / uploaded_file.name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(uploaded_file.getvalue())
            target_dataset = uploaded_file.name
        else:
            target_path = DATA_DIR / selected_dataset
        with st.spinner("Running data-quality checks and generating executive review output..."):
            log_lines = []
            status_plate = st.empty()
            for line in run_pipeline(str(target_path)):
                if line.startswith("[FINAL_EXIT_CODE]") or line.startswith("[PROCESS_COMPLETE]"):
                    continue
                log_lines.append(line)
                status_plate.code("\n".join(log_lines[-60:]), language="text")
            final_log = "\n".join(log_lines)
            st.session_state.pipeline_log = final_log
            st.session_state.pipeline_status = "Completed successfully" if "[PROCESS_COMPLETE]" in final_log else "Failed"
            st.session_state.metrics = parse_pipeline_log(final_log)
        st.rerun()

    st.markdown("---")
    st.caption("Current process state")
    st.write(st.session_state.pipeline_status)

    if st.session_state.pipeline_log:
        with st.expander("Detailed runtime log"):
            st.code(st.session_state.pipeline_log, language="text")

st.markdown("---")

if not locate_flagged_csv():
    st.warning("No review output available yet. Select a dataset and run the workflow to generate the review pack.")
    st.stop()

flagged_df, csv_path = load_flagged_data()
if flagged_df.empty:
    st.warning("The flagged output is empty. Please rerun the workflow with a valid clinical dataset.")
    st.stop()

st.subheader("Executive overview")
col_a, col_b, col_c, col_d = st.columns(4)
review_total = int(st.session_state.metrics.get("total") or len(flagged_df) + 0)
flagged_total = int(flagged_df.shape[0])
high_priority = int(flagged_df[flagged_df["severity"] == "high"].shape[0]) if "severity" in flagged_df.columns else 0
issue_count = int(flagged_df["issue_type"].nunique() if "issue_type" in flagged_df.columns else 0)

for col, label, value in [
    (col_a, "Reviewed records", review_total),
    (col_b, "Flagged records", flagged_total),
    (col_c, "High priority", high_priority),
    (col_d, "Unique issue types", issue_count),
]:
    with col:
        st.markdown('<div class="kpi">', unsafe_allow_html=True)
        st.metric(label, value)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

with st.container():
    st.subheader("Review performance by signal")
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Issue intelligence", "Review queue", "Site queries"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            sev_counts = flagged_df["severity"].value_counts().rename_axis("severity").reset_index(name="count")
            sev_counts["severity"] = sev_counts["severity"].str.title()
            sev_fig = px.bar(
                sev_counts,
                x="severity",
                y="count",
                color="severity",
                color_discrete_map={
                    "High": SEVERITY_COLORS["high"],
                    "Medium": SEVERITY_COLORS["medium"],
                    "Low": SEVERITY_COLORS["low"],
                    "Unknown": SEVERITY_COLORS["unknown"],
                },
                title="Severity Distribution by Clinical Risk",
                template="plotly_dark",
            )
            sev_fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(sev_fig, use_container_width=True)

        with col2:
            source_counts = flagged_df["source"].value_counts().rename_axis("source").reset_index(name="count")
            source_fig = px.pie(
                source_counts,
                names="source",
                values="count",
                title="Flagged Volume by Source",
                color_discrete_sequence=px.colors.sequential.Aggrnyl,
                hole=0.35,
            )
            source_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(source_fig, use_container_width=True)

    with tab2:
        issue_counts = flagged_df["issue_type"].value_counts().rename_axis("issue_type").reset_index(name="count")
        issue_fig = px.bar(
            issue_counts,
            x="count",
            y="issue_type",
            orientation="h",
            title="Issue Type Breakdown",
            color="issue_type",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            template="plotly_dark",
        )
        issue_fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(issue_fig, use_container_width=True)

    with tab3:
        queue_df = flagged_df[["record_id", "patient_id", "source", "field_name", "issue_type", "severity"]].copy()
        queue_df = queue_df.sort_values(["severity", "source"], ascending=[False, True])
        st.dataframe(queue_df, use_container_width=True, hide_index=True)

    with tab4:
        query_df = flagged_df[["record_id", "patient_id", "source", "field_name", "issue_type", "severity", "drafted_query"]].copy()
        st.dataframe(query_df, use_container_width=True, hide_index=True)

st.markdown("---")

st.subheader("Operational review table")
show_df = flagged_df.copy()
if "drafted_query" in show_df.columns:
    show_df["drafted_query"] = show_df["drafted_query"].fillna("N/A").str.slice(0, 170)
show_df = show_df[["record_id", "patient_id", "source", "field_name", "issue_type", "severity", "drafted_query"]]
st.dataframe(show_df, use_container_width=True, hide_index=True)

st.caption(f"Latest data source: {selected_dataset} | Output file: {csv_path}")

st.markdown("---")

if st.button("Export executive review pack", use_container_width=True):
    export_df = flagged_df.copy()
    export_path = OUTPUT_DIR / "clinical_review_exec_summary.csv"
    export_df.to_csv(export_path, index=False)
    st.success(f"Executive review pack exported to {export_path}")

    summary_df = export_df.groupby(["source", "severity"], as_index=False).size().rename(columns={"size": "flagged_count"})
    pdf_path = OUTPUT_DIR / "clinical_review_exec_summary.pdf"
    export_pdf(export_df, summary_df, str(pdf_path))
    st.success(f"PDF summary exported to {pdf_path}")
