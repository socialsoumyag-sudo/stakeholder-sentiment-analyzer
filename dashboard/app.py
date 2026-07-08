"""
Streamlit Dashboard — Stakeholder Sentiment & Roadmap Risk Analyzer
---------------------------------------------------------------------
Visualizes:
  - Per-stakeholder risk-tag timeline across weeks
  - Stakeholder conflict map
  - Pre-emptive risk flags with source citations
  - Suggested roadmap adjustment

Run with:
    streamlit run dashboard/app.py

Expects data/pipeline_output.json to exist (run orchestrator.py first).
"""

import json
import os
import sys

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

st.set_page_config(page_title="Stakeholder Sentiment & Roadmap Risk", layout="wide")

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pipeline_output.json")

CATEGORY_COLORS = {
    "none": "#2e7d32",
    "hedging": "#f9a825",
    "deflection": "#ef6c00",
    "over_confidence": "#c62828",
    "escalation_avoidance": "#8e24aa",
    "conflicting_priorities": "#1565c0",
    "ERROR": "#616161",
}


def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    with open(DATA_PATH) as f:
        return json.load(f)


def render_header():
    st.title("📊 Stakeholder Sentiment & Roadmap Risk Analyzer")
    st.caption(
        "Detects hedging, deflection, over-confidence, escalation-avoidance, and "
        "conflicting priorities across stakeholder status reports — then synthesizes "
        "a forward-looking roadmap risk view."
    )


def render_no_data_state():
    st.warning(
        "No pipeline output found yet. Run the pipeline first:\n\n"
        "```\nexport ANTHROPIC_API_KEY=sk-...\npython orchestrator.py\n```"
    )
    st.info(
        "This dashboard reads from `data/pipeline_output.json`, which is generated "
        "by running the classifier + synthesis agents over the synthetic status reports."
    )


def render_timeline(classified):
    st.subheader("Per-Stakeholder Risk Timeline")
    df = pd.DataFrame(classified)
    df = df[df["category"] != "ERROR"]

    stakeholders = sorted(df["stakeholder"].unique())
    for sh in stakeholders:
        sub = df[df["stakeholder"] == sh].sort_values("week")
        cols = st.columns([1] + [1] * len(sub))
        cols[0].markdown(f"**{sh}**  \n*{sub.iloc[0]['role']}*")
        for i, (_, row) in enumerate(sub.iterrows(), start=1):
            color = CATEGORY_COLORS.get(row["category"], "#999")
            with cols[i]:
                st.markdown(
                    f"<div style='background:{color}22;border-left:4px solid {color};"
                    f"padding:6px;border-radius:4px;font-size:0.8em'>"
                    f"<b>{row['week']}</b><br>{row['category']}<br>"
                    f"<i>conf: {row['confidence']:.2f}</i></div>",
                    unsafe_allow_html=True,
                )
                with st.expander("statement"):
                    st.write(row["text"])
                    st.caption(row["rationale"])


def render_conflict_map(conflicts):
    st.subheader("⚔️ Stakeholder Conflict Map")
    if not conflicts:
        st.info("No conflicts detected in this dataset.")
        return
    for c in conflicts:
        with st.container(border=True):
            st.markdown(f"**{' vs '.join(c['stakeholders'])}**")
            st.write(c["issue"])
            for ev in c.get("evidence", []):
                st.caption(f'"{ev}"')


def render_risk_flags(flags):
    st.subheader("🚩 Pre-emptive Risk Flags")
    if not flags:
        st.info("No risk flags raised.")
        return
    for f in sorted(flags, key=lambda x: -x.get("confidence", 0)):
        conf = f.get("confidence", 0)
        bar_color = "#c62828" if conf > 0.7 else "#f9a825" if conf > 0.4 else "#2e7d32"
        with st.container(border=True):
            st.markdown(f"**{f['risk']}**  \n"
                        f"<span style='color:{bar_color}'>Confidence: {conf:.0%}</span>",
                        unsafe_allow_html=True)
            st.write(f"→ {f['recommended_action']}")
            with st.expander("source statements"):
                for s in f.get("source_statements", []):
                    st.caption(f'"{s}"')


def render_roadmap(adjustment):
    st.subheader("🗺️ Suggested Roadmap Adjustment")
    st.markdown(adjustment)


def main():
    render_header()
    data = load_data()
    if not data:
        render_no_data_state()
        return

    classified = data.get("classified_statements", [])
    synthesis = data.get("synthesis", {})

    render_timeline(classified)
    st.divider()

    if synthesis.get("error"):
        st.error(f"Synthesis step failed: {synthesis['error']}")
        return

    col1, col2 = st.columns(2)
    with col1:
        render_conflict_map(synthesis.get("conflict_map", []))
    with col2:
        render_risk_flags(synthesis.get("risk_flags", []))

    st.divider()
    render_roadmap(synthesis.get("roadmap_adjustment", "_No adjustment generated._"))


if __name__ == "__main__":
    main()
