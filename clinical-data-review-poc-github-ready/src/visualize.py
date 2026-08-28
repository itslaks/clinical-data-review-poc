"""Create an advanced dashboard for the clinical review output."""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _safe_df(df):
    if df is None:
        return None
    if hasattr(df, "collect"):
        try:
            return pd.DataFrame([row.asDict() for row in df.collect()])
        except Exception:
            return None
    return df


def save_dashboard(summary_df, flagged_df, output_dir):
    """Build a polished dashboard PNG for the review results."""
    output_dir = os.path.abspath(str(output_dir))
    summary_pdf = _safe_df(summary_df)
    flagged_pdf = _safe_df(flagged_df)

    viz_dir = os.path.join(output_dir, "visualizations")
    os.makedirs(viz_dir, exist_ok=True)

    if summary_pdf is None and flagged_pdf is None:
        return os.path.join(viz_dir, "clinical_review_dashboard.png")

    plt.style.use("seaborn-v0_8-whitegrid")

    fig = plt.figure(figsize=(16, 10), facecolor="#f4f7fb")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1])

    # Header
    header = fig.add_subplot(gs[0, :])
    header.axis("off")
    header.text(
        0.02,
        0.72,
        "Clinical Data Review Dashboard",
        fontsize=24,
        fontweight="bold",
        color="#0f172a",
    )
    header.text(
        0.02,
        0.38,
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        fontsize=11,
        color="#475569",
    )

    total_records = 0
    total_flagged = 0
    if flagged_pdf is not None:
        total_flagged = len(flagged_pdf)
    if summary_pdf is not None:
        total_records = int(summary_pdf.get("total_records", 0).sum()) if "total_records" in summary_pdf.columns else 0

    metric_box = fig.add_axes([0.63, 0.6, 0.30, 0.20])
    metric_box.axis("off")
    metrics = [
        ("Flagged", total_flagged, "#ef4444"),
        ("Severity high", "", "#dc2626"),
        ("Severity medium", "", "#f59e0b"),
    ]
    if summary_pdf is not None:
        high_count = int(summary_pdf[summary_pdf["severity"] == "high"]["flagged_count"].sum()) if "severity" in summary_pdf.columns else 0
        medium_count = int(summary_pdf[summary_pdf["severity"] == "medium"]["flagged_count"].sum()) if "severity" in summary_pdf.columns else 0
        metrics = [
            ("Flagged", total_flagged, "#ef4444"),
            ("High", high_count, "#dc2626"),
            ("Medium", medium_count, "#f59e0b"),
        ]

    y = 0.75
    for label, value, color in metrics:
        metric_box.text(0.0, y, f"{label}", fontsize=11, color="#475569")
        metric_box.text(0.7, y, f"{value}", fontsize=20, fontweight="bold", color=color)
        y -= 0.25

    # Severity counts chart
    ax1 = fig.add_subplot(gs[1, 0])
    if summary_pdf is not None and "severity" in summary_pdf.columns:
        sev = summary_pdf.groupby("severity", as_index=False)["flagged_count"].sum().sort_values("flagged_count", ascending=False)
        colors = ["#ef4444" if s == "high" else "#f59e0b" for s in sev["severity"]]
        ax1.bar(sev["severity"], sev["flagged_count"], color=colors, edgecolor="#0f172a", linewidth=0.8)
        ax1.set_title("Flagged counts by severity", color="#0f172a", fontsize=13, fontweight="bold")
        ax1.set_ylabel("Records")
        ax1.set_xlabel("Severity")
        ax1.grid(axis="y", linestyle="--", alpha=0.35)
    else:
        ax1.text(0.5, 0.5, "No severity summary available", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_axis_off()

    # Source counts chart
    ax2 = fig.add_subplot(gs[1, 1])
    if summary_pdf is not None and "source" in summary_pdf.columns:
        src = summary_pdf.groupby("source", as_index=False)["flagged_count"].sum().sort_values("flagged_count", ascending=False)
        colors = ["#3b82f6", "#8b5cf6", "#10b981", "#f97316", "#ec4899", "#94a3b8"][: len(src)]
        ax2.barh(src["source"], src["flagged_count"], color=colors, edgecolor="#0f172a", linewidth=0.8)
        ax2.set_title("Flagged counts by source", color="#0f172a", fontsize=13, fontweight="bold")
        ax2.set_xlabel("Records")
        ax2.invert_yaxis()
        ax2.grid(axis="x", linestyle="--", alpha=0.35)
    else:
        ax2.text(0.5, 0.5, "No source summary available", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_axis_off()

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    dashboard_path = os.path.join(viz_dir, "clinical_review_dashboard.png")
    fig.savefig(dashboard_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return dashboard_path
